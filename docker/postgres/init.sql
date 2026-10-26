CREATE USER order_service_user WITH PASSWORD 'order_service_pass';
CREATE USER restaurant_service_user WITH PASSWORD 'restaurant_service_pass';
CREATE USER payment_service_user WITH PASSWORD 'payment_service_pass';
CREATE USER delivery_service_user WITH PASSWORD 'delivery_service_pass';
CREATE USER notification_service_user WITH PASSWORD 'notification_service_pass';

CREATE DATABASE order_service_db OWNER order_service_user;
CREATE DATABASE restaurant_service_db OWNER restaurant_service_user;
CREATE DATABASE payment_service_db OWNER payment_service_user;
CREATE DATABASE delivery_service_db OWNER delivery_service_user;
CREATE DATABASE notification_service_db OWNER notification_service_user;

GRANT ALL PRIVILEGES ON DATABASE order_service_db TO order_service_user;
GRANT ALL PRIVILEGES ON DATABASE restaurant_service_db TO restaurant_service_user;
GRANT ALL PRIVILEGES ON DATABASE payment_service_db TO payment_service_user;
GRANT ALL PRIVILEGES ON DATABASE delivery_service_db TO delivery_service_user;
GRANT ALL PRIVILEGES ON DATABASE notification_service_db TO notification_service_user;
