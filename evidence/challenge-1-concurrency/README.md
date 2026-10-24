# Challenge 1 Evidence: Concurrency Control

## 1. Problem Statement
In high-demand food delivery platforms, multiple customers frequently attempt to order the same popular menu item (e.g., flash deals, daily chef specials, or limited portions) at the exact same millisecond. If the system is not properly engineered with database-level concurrency controls, simultaneous requests will over-allocate the item, selling more units than exist in physical inventory.

## 2. Why Plain "Check-Then-Update" in Application Code Fails
A naive implementation typically performs:
```python
# Race condition hazard (Anti-pattern):
item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
if item.available_quantity >= requested_qty:
    item.available_quantity -= requested_qty
    db.commit()
```
When 20 concurrent threads execute this simultaneously:
1. All 20 threads read `available_quantity = 5` concurrently before any thread has committed its deduction.
2. All 20 threads evaluate `5 >= 1` as `True`.
3. All 20 threads decrement the in-memory value and commit.
4. **Outcome**: 20 orders succeed for a capacity of 5. The final stock is over-allocated to -15, resulting in overselling and dissatisfied customers.

## 3. Implemented Solution: Atomic Conditional SQL Update
In FoodFlow's `Restaurant Service`, stock decrement is executed as an **atomic conditional update** at the database engine level:
```sql
UPDATE menu_items 
SET available_quantity = available_quantity - :qty,
    version = version + 1
WHERE id = :item_id AND available_quantity >= :qty;
```
* The database engine acquires an atomic row lock during the `UPDATE`.
* The condition `available_quantity >= :qty` is evaluated at write time.
* If `rowcount == 0`, either the item does not exist or the remaining stock is insufficient. The transaction rolls back and immediately returns `HTTP 409 Conflict` with diagnostic message: `"Stock insufficient: requested X, only Y remaining."`
* Because the check and update occur in a single atomic database statement, race conditions are mathematically eliminated.

## 4. Test Script & Repeatable Verification
* **Script**: `scripts/test_challenge1_concurrency.py`
* **Test Parameter**: Contended dish capacity $N = 5$.
* **Parallel Requests**: 20 simultaneous threads dispatched using `concurrent.futures.ThreadPoolExecutor`.
* **Observed Output**: [concurrency_run_output.txt](concurrency_run_output.txt)
  * Requests #01 to #05 succeeded with `HTTP 201 Created` (`status = "RESERVED"`).
  * Requests #06 to #20 were rejected with `HTTP 409 Conflict` (`"Stock insufficient: requested 1, only 0 remaining"`).
  * **Final Database Available Quantity**: Exactly `0`.
  * **Final Database Version**: `6` (initial 1 + 5 increments).
  * **Over-allocation**: Exactly `0`.
