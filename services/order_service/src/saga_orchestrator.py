import uuid
import httpx
from sqlalchemy.orm import Session
from .config import config
from .models import Order, OrderStateLog
from .middleware import logger

class SagaOrchestrator:
    def __init__(self, db: Session, correlation_id: str = "N/A"):
        self.db = db
        self.correlation_id = correlation_id
        self.headers = {
            "X-Correlation-ID": correlation_id,
            "Content-Type": "application/json"
        }

    def _transition(self, order: Order, new_state: str, note: str = ""):
        old_state = order.status
        order.status = new_state
        log_entry = OrderStateLog(
            id=str(uuid.uuid4()),
            order_id=order.id,
            from_state=old_state,
            to_state=new_state,
            note=note
        )
        self.db.add(log_entry)
        self.db.commit()
        self.db.refresh(order)
        logger.info(
            f"SAGA STATE TRANSITION [order_id={order.id}]: {old_state} -> {new_state} ({note})",
            extra={"correlation_id": self.correlation_id}
        )

    def execute_order_saga(
        self,
        order: Order,
        card_number: str = "4111111111111111",
        mock_payment_fail: bool = False
    ) -> bool:
        """
        Executes the Orchestrated Saga for FoodFlow order checkout.
        Steps:
          1. Reserve Stock (Restaurant Service)
          2. Charge Payment (Payment Service)
          3. Assign Rider (Delivery Service)
          4. Confirm Reservation & Notify (Restaurant & Notification Services)
        Compensating actions are triggered sequentially if any step fails.
        """
        logger.info(
            f"Initiating Checkout Saga for Order {order.id} (Total: ${order.total_amount})",
            extra={"correlation_id": self.correlation_id}
        )

        with httpx.Client(timeout=5.0) as client:
            # -------------------------------------------------------------
            # STEP 1: Reserve Stock in Restaurant Service
            # -------------------------------------------------------------
            logger.info("Saga Step 1: Reserving stock in Restaurant Service...", extra={"correlation_id": self.correlation_id})
            try:
                res_payload = {
                    "order_id": order.id,
                    "restaurant_id": order.restaurant_id,
                    "item_id": order.item_id,
                    "quantity": order.quantity
                }
                res_resp = client.post(
                    f"{config.RESTAURANT_SERVICE_URL}/api/v1/restaurants/reservations",
                    json=res_payload,
                    headers=self.headers
                )

                if res_resp.status_code != 201:
                    err_msg = res_resp.json().get("error", {}).get("message", "Stock reservation failed")
                    order.failure_reason = err_msg
                    self._transition(order, "FAILED_OUT_OF_STOCK", err_msg)
                    return False

                reservation_data = res_resp.json()
                order.reservation_id = reservation_data["id"]
                self._transition(order, "STOCK_RESERVED", f"Reservation ID: {order.reservation_id}")

            except Exception as e:
                err_msg = f"Network failure connecting to Restaurant Service: {str(e)}"
                order.failure_reason = err_msg
                self._transition(order, "FAILED_OUT_OF_STOCK", err_msg)
                return False

            # -------------------------------------------------------------
            # STEP 2: Charge Payment in Payment Service
            # -------------------------------------------------------------
            logger.info("Saga Step 2: Charging payment in Payment Service...", extra={"correlation_id": self.correlation_id})
            pay_headers = dict(self.headers)
            pay_headers["Idempotency-Key"] = f"pay-{order.id}"
            if mock_payment_fail:
                pay_headers["X-Mock-Fail"] = "true"

            try:
                pay_payload = {
                    "order_id": order.id,
                    "customer_id": order.customer_id,
                    "amount": order.total_amount,
                    "currency": "USD",
                    "payment_method": "CREDIT_CARD",
                    "card_number": card_number
                }
                pay_resp = client.post(
                    f"{config.PAYMENT_SERVICE_URL}/api/v1/payments/charge",
                    json=pay_payload,
                    headers=pay_headers
                )

                if pay_resp.status_code != 201:
                    err_msg = pay_resp.json().get("error", {}).get("message", "Payment processing failed")
                    logger.warning(
                        f"Saga Step 2 Failed: {err_msg}. Triggering Compensating Actions!",
                        extra={"correlation_id": self.correlation_id}
                    )
                    self._transition(order, "COMPENSATING_ROLLBACK", "Payment failed; releasing reserved stock")

                    # COMPENSATION: Release stock reservation
                    try:
                        rel_resp = client.post(
                            f"{config.RESTAURANT_SERVICE_URL}/api/v1/restaurants/reservations/{order.reservation_id}/release",
                            headers=self.headers
                        )
                        logger.info(
                            f"Compensation Release Stock result: {rel_resp.status_code}",
                            extra={"correlation_id": self.correlation_id}
                        )
                    except Exception as comp_err:
                        logger.error(
                            f"CRITICAL: Failed to release stock during compensation: {comp_err}",
                            extra={"correlation_id": self.correlation_id}
                        )

                    order.failure_reason = err_msg
                    self._transition(order, "FAILED_PAYMENT_REJECTED", err_msg)
                    return False

                payment_data = pay_resp.json()
                order.payment_id = payment_data["id"]
                self._transition(order, "PAID", f"Payment ID: {order.payment_id}")

            except Exception as e:
                err_msg = f"Network failure connecting to Payment Service: {str(e)}"
                logger.warning(
                    f"Saga Step 2 Network Error: {err_msg}. Triggering Compensating Actions!",
                    extra={"correlation_id": self.correlation_id}
                )
                self._transition(order, "COMPENSATING_ROLLBACK", "Payment unreachable; releasing stock")
                try:
                    client.post(
                        f"{config.RESTAURANT_SERVICE_URL}/api/v1/restaurants/reservations/{order.reservation_id}/release",
                        headers=self.headers
                    )
                except Exception:
                    pass
                order.failure_reason = err_msg
                self._transition(order, "FAILED_PAYMENT_REJECTED", err_msg)
                return False

            # -------------------------------------------------------------
            # STEP 3: Assign Delivery Rider in Delivery Service
            # -------------------------------------------------------------
            logger.info("Saga Step 3: Assigning delivery rider...", extra={"correlation_id": self.correlation_id})
            try:
                deliv_payload = {
                    "order_id": order.id,
                    "pickup_address": order.pickup_address,
                    "delivery_address": order.delivery_address
                }
                deliv_resp = client.post(
                    f"{config.DELIVERY_SERVICE_URL}/api/v1/deliveries/tasks",
                    json=deliv_payload,
                    headers=self.headers
                )

                if deliv_resp.status_code != 201:
                    err_msg = deliv_resp.json().get("error", {}).get("message", "No rider available")
                    logger.warning(
                        f"Saga Step 3 Failed: {err_msg}. Triggering Compensating Actions for Payment & Stock!",
                        extra={"correlation_id": self.correlation_id}
                    )
                    self._transition(order, "COMPENSATING_ROLLBACK", "No rider; refunding payment and releasing stock")

                    # COMPENSATION 1: Refund payment
                    try:
                        ref_resp = client.post(
                            f"{config.PAYMENT_SERVICE_URL}/api/v1/payments/{order.payment_id}/refund",
                            json={"reason": "Delivery rider unavailable compensation"},
                            headers=self.headers
                        )
                        logger.info(f"Compensation Refund result: {ref_resp.status_code}", extra={"correlation_id": self.correlation_id})
                    except Exception as ref_err:
                        logger.error(f"Failed to refund payment during compensation: {ref_err}", extra={"correlation_id": self.correlation_id})

                    # COMPENSATION 2: Release stock reservation
                    try:
                        rel_resp = client.post(
                            f"{config.RESTAURANT_SERVICE_URL}/api/v1/restaurants/reservations/{order.reservation_id}/release",
                            headers=self.headers
                        )
                        logger.info(f"Compensation Release Stock result: {rel_resp.status_code}", extra={"correlation_id": self.correlation_id})
                    except Exception as rel_err:
                        logger.error(f"Failed to release stock during compensation: {rel_err}", extra={"correlation_id": self.correlation_id})

                    order.failure_reason = err_msg
                    self._transition(order, "FAILED_NO_RIDER_AVAILABLE", err_msg)
                    return False

                delivery_data = deliv_resp.json()
                order.delivery_task_id = delivery_data["id"]
                self._transition(order, "DELIVERY_ASSIGNED", f"Delivery Task ID: {order.delivery_task_id}")

            except Exception as e:
                err_msg = f"Network failure connecting to Delivery Service: {str(e)}"
                self._transition(order, "COMPENSATING_ROLLBACK", "Delivery unreachable; compensating")
                try:
                    client.post(
                        f"{config.PAYMENT_SERVICE_URL}/api/v1/payments/{order.payment_id}/refund",
                        json={"reason": "Delivery unreachable compensation"},
                        headers=self.headers
                    )
                    client.post(
                        f"{config.RESTAURANT_SERVICE_URL}/api/v1/restaurants/reservations/{order.reservation_id}/release",
                        headers=self.headers
                    )
                except Exception:
                    pass
                order.failure_reason = err_msg
                self._transition(order, "FAILED_NO_RIDER_AVAILABLE", err_msg)
                return False

            # -------------------------------------------------------------
            # STEP 4: Confirm Reservation & Send Notification (Happy Path Finalization)
            # -------------------------------------------------------------
            logger.info("Saga Step 4: Finalizing order and dispatching notifications...", extra={"correlation_id": self.correlation_id})
            # Confirm reservation permanently
            try:
                client.post(
                    f"{config.RESTAURANT_SERVICE_URL}/api/v1/restaurants/reservations/{order.reservation_id}/confirm",
                    headers=self.headers
                )
            except Exception as e:
                logger.warning(f"Could not confirm reservation permanently: {e}", extra={"correlation_id": self.correlation_id})

            # Send Notification (Graceful degradation: failure to send SMS does not abort paid order)
            try:
                notif_payload = {
                    "order_id": order.id,
                    "recipient": f"customer-{order.customer_id}@example.com",
                    "channel": "SMS",
                    "message": f"FoodFlow Order {order.id} confirmed! Delivery task {order.delivery_task_id} is dispatched."
                }
                client.post(
                    f"{config.NOTIFICATION_SERVICE_URL}/api/v1/notifications/send",
                    json=notif_payload,
                    headers=self.headers
                )
            except Exception as e:
                logger.warning(f"Notification service call failed (non-critical): {e}", extra={"correlation_id": self.correlation_id})

            self._transition(order, "CONFIRMED", "Order checkout saga successfully finished")
            return True
