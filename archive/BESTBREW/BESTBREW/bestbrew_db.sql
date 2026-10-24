-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: May 08, 2026 at 03:51 AM
-- Server version: 10.4.32-MariaDB
-- PHP Version: 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `bestbrew_db`
--

DELIMITER $$
--
-- Procedures
--
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_complete_order` (IN `p_order_id` INT)   BEGIN
    DECLARE v_report_date DATE;

    UPDATE orders
    SET status = 'Completed'
    WHERE order_id = p_order_id
      AND status <> 'Cancelled';

    SELECT DATE(created_at)
      INTO v_report_date
    FROM orders
    WHERE order_id = p_order_id
    LIMIT 1;

    IF v_report_date IS NOT NULL THEN
        INSERT INTO daily_reports (report_date, total_sales, total_orders)
        SELECT
            v_report_date,
            COALESCE(SUM(total_amount), 0),
            COUNT(*)
        FROM orders
        WHERE DATE(created_at) = v_report_date
          AND status = 'Completed'
        ON DUPLICATE KEY UPDATE
            total_sales = VALUES(total_sales),
            total_orders = VALUES(total_orders),
            generated_at = CURRENT_TIMESTAMP;
    END IF;

    SELECT
        o.order_id,
        fn_format_order_code(o.order_id) AS order_code,
        COALESCE(u.full_name, u.username, 'Walk-in Customer') AS full_name,
        COALESCE(c.category_name, 'Uncategorized') AS category_name,
        COALESCE(p.product_name, 'No Product') AS product_name,
        oi.size_label,
        COALESCE(oi.quantity, 0) AS quantity,
        COALESCE(oi.unit_price, 0.00) AS unit_price,
        COALESCE(oi.line_total, 0.00) AS line_total,
        o.status,
        o.created_at
    FROM orders o
    LEFT JOIN users u ON u.user_id = o.user_id
    LEFT JOIN order_items oi ON oi.order_id = o.order_id
    LEFT JOIN products p ON p.product_id = oi.product_id
    LEFT JOIN categories c ON c.category_id = p.category_id
    WHERE o.order_id = p_order_id;
END$$

CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_get_bestsellers` ()   BEGIN
    SELECT product_name AS item_name, total_qty, 'PRODUCT' AS item_type
    FROM view_product_sales
    UNION ALL
    SELECT a.addon_name AS item_name, COALESCE(SUM(oia.quantity),0) AS total_qty, 'ADDON' AS item_type
    FROM addons a
    LEFT JOIN order_item_addons oia ON oia.addon_id = a.addon_id
    GROUP BY a.addon_id, a.addon_name
    ORDER BY total_qty DESC, item_name;
END$$

CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_get_sales_summary` ()   BEGIN
    SELECT
        (SELECT COUNT(*) FROM products WHERE is_active = 1) AS total_products,
        COUNT(DISTINCT o.order_id) AS todays_orders,
        COALESCE(SUM(o.total_amount), 0) AS total_revenue_today,
        (SELECT COUNT(*) FROM inventory WHERE quantity_on_hand <= reorder_level) AS low_stock_items
    FROM orders o
    WHERE DATE(o.created_at) = CURDATE();
END$$

CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_refresh_daily_report` ()   BEGIN
    INSERT INTO daily_reports (report_date, total_sales, total_orders)
    SELECT
        src.sales_date,
        ROUND(SUM(src.total_sales), 2) AS total_sales,
        SUM(src.total_orders) AS total_orders
    FROM (
        SELECT
            DATE(created_at) AS sales_date,
            total_amount AS total_sales,
            1 AS total_orders
        FROM orders
        WHERE status = 'Completed'

        UNION ALL

        SELECT
            CURDATE() AS sales_date,
            0.00 AS total_sales,
            0 AS total_orders
    ) AS src
    GROUP BY src.sales_date
    ON DUPLICATE KEY UPDATE
        total_sales = VALUES(total_sales),
        total_orders = VALUES(total_orders),
        generated_at = CURRENT_TIMESTAMP;

    SELECT
        report_date AS sales_date,
        total_orders,
        total_sales,
        CASE
            WHEN total_orders = 0 THEN 0.00
            ELSE ROUND(total_sales / total_orders, 2)
        END AS avg_order_value
    FROM daily_reports
    ORDER BY report_date DESC;
END$$

--
-- Functions
--
CREATE DEFINER=`root`@`localhost` FUNCTION `fn_compute_change` (`cash_amount` DECIMAL(10,2), `total_amount` DECIMAL(10,2)) RETURNS DECIMAL(10,2) DETERMINISTIC BEGIN
    RETURN cash_amount - total_amount;
END$$

CREATE DEFINER=`root`@`localhost` FUNCTION `fn_format_order_code` (`p_order_id` INT) RETURNS VARCHAR(20) CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci DETERMINISTIC BEGIN
    RETURN CONCAT('BB-', LPAD(p_order_id, 6, '0'));
END$$

CREATE DEFINER=`root`@`localhost` FUNCTION `fn_stock_status` (`qty` DECIMAL(10,2), `reorder_qty` DECIMAL(10,2)) RETURNS VARCHAR(20) CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci DETERMINISTIC BEGIN
    IF qty <= 0 THEN
        RETURN 'OUT OF STOCK';
    ELSEIF qty <= reorder_qty THEN
        RETURN 'LOW STOCK';
    END IF;
    RETURN 'IN STOCK';
END$$

DELIMITER ;

-- --------------------------------------------------------

--
-- Table structure for table `addons`
--

CREATE TABLE `addons` (
  `addon_id` int(11) NOT NULL,
  `addon_name` varchar(100) NOT NULL,
  `price` decimal(10,2) NOT NULL DEFAULT 9.00,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `addon_price` decimal(10,2) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `addons`
--

INSERT INTO `addons` (`addon_id`, `addon_name`, `price`, `is_active`, `addon_price`) VALUES
(2285, 'Pearl', 9.00, 1, 15.00),
(2286, 'Crushed Oreo', 9.00, 1, 15.00),
(2287, 'Crushed Graham', 9.00, 1, 15.00),
(2288, 'Crystal', 9.00, 1, 15.00);

-- --------------------------------------------------------

--
-- Table structure for table `categories`
--

CREATE TABLE `categories` (
  `category_id` int(11) NOT NULL,
  `category_name` varchar(80) NOT NULL,
  `description` varchar(255) DEFAULT NULL,
  `price_small` decimal(10,2) DEFAULT NULL,
  `price_large` decimal(10,2) DEFAULT NULL,
  `icon_emoji` varchar(10) DEFAULT '?',
  `is_active` tinyint(1) NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `categories`
--

INSERT INTO `categories` (`category_id`, `category_name`, `description`, `price_small`, `price_large`, `icon_emoji`, `is_active`) VALUES
(1, 'Milkshake Cream Base', 'Milkshake cream base flavors, 49/59 pesos', 49.00, 59.00, '🥤', 1),
(2, 'Milkshake Coffee Base', 'Coffee base flavors, 49/59 pesos', 49.00, 59.00, '☕', 1),
(3, 'Milktea', 'Milktea flavors, 29/39 pesos', 29.00, 39.00, '🧋', 1),
(4, 'Fruit Tea', 'Fruit tea flavors, 29/39 pesos', 29.00, 39.00, '🍓', 1),
(5, 'Iced Coffee', 'Iced coffee flavors, 29/39 pesos', 29.00, 39.00, '🧊', 1),
(6, 'Test Category', 'Test Category products', NULL, NULL, '🧋', 1),
(7, 'DB Category', 'DB Category products', NULL, NULL, '🧋', 1),
(8, 'Classic', 'Classic products', NULL, NULL, '🧋', 1);

-- --------------------------------------------------------

--
-- Table structure for table `daily_reports`
--

CREATE TABLE `daily_reports` (
  `report_id` int(11) NOT NULL,
  `report_date` date NOT NULL,
  `total_sales` decimal(10,2) NOT NULL DEFAULT 0.00,
  `total_orders` int(11) NOT NULL DEFAULT 0,
  `generated_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `daily_reports`
--

INSERT INTO `daily_reports` (`report_id`, `report_date`, `total_sales`, `total_orders`, `generated_at`) VALUES
(1, '2026-04-26', 0.00, 0, '2026-04-26 11:42:41');

-- --------------------------------------------------------

--
-- Table structure for table `inventory`
--

CREATE TABLE `inventory` (
  `inventory_id` int(11) NOT NULL,
  `inventory_name` varchar(100) NOT NULL,
  `category` varchar(60) NOT NULL,
  `unit_name` varchar(30) NOT NULL,
  `quantity_on_hand` decimal(10,2) NOT NULL DEFAULT 0.00,
  `reorder_level` decimal(10,2) NOT NULL DEFAULT 0.00,
  `last_restocked` date DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `inventory`
--

INSERT INTO `inventory` (`inventory_id`, `inventory_name`, `category`, `unit_name`, `quantity_on_hand`, `reorder_level`, `last_restocked`) VALUES
(1, 'Whip Cream', 'Base Ingredient', 'kg', 21.00, 8.00, '2026-05-08'),
(2, 'Tea', 'Base Ingredient', 'kg', 24.00, 20.00, '2026-04-30'),
(3, 'Creamer', 'Dairy', 'kg', 20.00, 8.00, '2026-05-08'),
(4, 'Fructose', 'Sweetener', 'liters', 20.00, 10.00, '2026-05-08'),
(5, 'Taro Powder', 'Flavoring', 'kg', 10.00, 10.00, '2026-04-27'),
(6, 'Strawberry Powder', 'Flavoring', 'kg', 9.00, 8.00, '2026-04-15'),
(7, 'Cheesecake Powder', 'Flavoring', 'kg', 11.00, 8.00, '2026-04-27'),
(8, 'Cookies and Cream Powder', 'Flavoring', 'kg', 11.00, 8.00, '2026-05-08'),
(9, 'Java Chips Powder', 'Flavoring', 'kg', 8.00, 8.00, '2026-04-15'),
(10, 'Chocolate Powder', 'Flavoring', 'kg', 12.00, 10.00, '2026-04-15'),
(11, 'Double Dutch Powder', 'Flavoring', 'kg', 27.00, 8.00, '2026-04-30'),
(12, 'Choco Nutella Powder', 'Flavoring', 'kg', 18.00, 8.00, '2026-04-30'),
(13, 'Triple Choco Powder', 'Flavoring', 'kg', 20.00, 8.00, '2026-04-30'),
(14, 'Avocado Powder', 'Flavoring', 'kg', 27.00, 8.00, '2026-05-06'),
(15, 'Cappuccino Powder', 'Flavoring', 'kg', 9.00, 8.00, '2026-04-15'),
(16, 'Caramel Macchiato Powder', 'Flavoring', 'liters', 9.00, 8.00, '2026-04-15'),
(17, 'Dark Chocolate Powder', 'Flavoring', 'kg', 21.00, 8.00, '2026-05-07'),
(18, 'Matcha Powder', 'Flavoring', 'kg', 9.00, 8.00, '2026-04-15'),
(19, 'Wintermelon Powder', 'Flavoring', 'liters', 9.00, 8.00, '2026-04-15'),
(20, 'Okinawa Powder', 'Flavoring', 'liters', 9.00, 8.00, '2026-04-15'),
(21, 'Red Velvet Powder', 'Flavoring', 'kg', 9.00, 8.00, '2026-04-15'),
(22, 'Salted Caramel Powder', 'Flavoring', 'liters', 8.00, 8.00, '2026-04-15'),
(23, 'Black Forest Powder', 'Flavoring', 'kg', 9.00, 8.00, '2026-04-15'),
(24, 'Lemon Syrup', 'Fruit Syrup', 'liters', 10.00, 8.00, '2026-04-15'),
(25, 'Mango Syrup', 'Fruit Syrup', 'liters', 10.00, 8.00, '2026-04-15'),
(26, 'Lychee Syrup', 'Fruit Syrup', 'liters', 10.00, 8.00, '2026-04-15'),
(27, 'Kiwi Syrup', 'Fruit Syrup', 'liters', 10.00, 8.00, '2026-04-15'),
(28, 'Green Apple Syrup', 'Fruit Syrup', 'liters', 10.00, 8.00, '2026-04-15'),
(29, 'Blueberry Syrup', 'Fruit Syrup', 'liters', 10.00, 8.00, '2026-04-15'),
(30, 'Honey Peach Syrup', 'Fruit Syrup', 'liters', 8.00, 8.00, '2026-04-15'),
(31, 'Vanilla Powder', 'Flavoring', 'liters', 10.00, 8.00, '2026-04-15'),
(32, 'Coffee Powder', 'Coffee Ingredient', 'kg', 9.00, 8.00, '2026-04-15'),
(33, 'Pearl', 'Add Ons', 'kg', 38.00, 15.00, '2026-04-16'),
(34, 'Crystal', 'Add Ons', 'kg', 9.00, 8.00, '2026-04-16'),
(35, 'Crushed Oreo', 'Add Ons', 'kg', 11.00, 8.00, '2026-04-16'),
(36, 'Crushed Graham', 'Add Ons', 'kg', 24.00, 8.00, '2026-04-30'),
(37, 'Cups Large', 'Packaging', 'pcs', 496.00, 100.00, '2026-05-08'),
(38, 'Domelids', 'Packaging', 'pcs', 496.00, 100.00, '2026-05-08'),
(39, 'Straws', 'Packaging', 'pcs', 495.00, 100.00, '2026-05-08'),
(40, 'Sealing Film', 'Packaging', 'rolls', 8.00, 5.00, '2026-04-16'),
(41, 'Cups Small', 'Packaging', 'pcs', 493.00, 100.00, '2026-04-16'),
(42, 'Flatlids', 'Packaging', 'pcs', 493.00, 100.00, '2026-04-16'),
(43, 'Mosa', 'Packaging', 'pcs', 200.00, 100.00, '2026-04-16');

-- --------------------------------------------------------

--
-- Table structure for table `orders`
--

CREATE TABLE `orders` (
  `order_id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `status` enum('Pending','Preparing','Ready','Completed','Cancelled') NOT NULL DEFAULT 'Pending',
  `total_amount` decimal(10,2) NOT NULL DEFAULT 0.00,
  `cash_tendered` decimal(10,2) NOT NULL DEFAULT 0.00,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `order_items`
--

CREATE TABLE `order_items` (
  `order_item_id` int(11) NOT NULL,
  `order_id` int(11) NOT NULL,
  `product_id` int(11) NOT NULL,
  `size_label` enum('Small','Large') NOT NULL DEFAULT 'Small',
  `quantity` int(11) NOT NULL,
  `unit_price` decimal(10,2) NOT NULL,
  `line_total` decimal(10,2) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Triggers `order_items`
--
DELIMITER $$
CREATE TRIGGER `trg_after_order_item_insert` AFTER INSERT ON `order_items` FOR EACH ROW BEGIN
    UPDATE inventory i
    JOIN product_inventory pi ON pi.inventory_id = i.inventory_id
    SET i.quantity_on_hand = i.quantity_on_hand - (pi.quantity_required * NEW.quantity)
    WHERE pi.product_id = NEW.product_id;
END
$$
DELIMITER ;

-- --------------------------------------------------------

--
-- Table structure for table `order_item_addons`
--

CREATE TABLE `order_item_addons` (
  `order_item_addon_id` int(11) NOT NULL,
  `order_item_id` int(11) NOT NULL,
  `addon_id` int(11) NOT NULL,
  `quantity` int(11) NOT NULL DEFAULT 1,
  `line_total` decimal(10,2) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Table structure for table `products`
--

CREATE TABLE `products` (
  `product_id` int(11) NOT NULL,
  `category_id` int(11) NOT NULL,
  `product_name` varchar(100) NOT NULL,
  `price` decimal(10,2) NOT NULL,
  `price_small` decimal(10,2) DEFAULT NULL,
  `price_large` decimal(10,2) DEFAULT NULL,
  `icon_emoji` varchar(10) DEFAULT '?',
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `image_path` varchar(255) DEFAULT NULL,
  `description` varchar(255) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `products`
--

INSERT INTO `products` (`product_id`, `category_id`, `product_name`, `price`, `price_small`, `price_large`, `icon_emoji`, `is_active`, `image_path`, `description`) VALUES
(1, 1, 'Taro', 49.00, 49.00, 59.00, '🥤', 1, 'assets/products/2022d76b-e69d-4df7-a2c7-461733f743a3_655f040e.jpg', 'No description'),
(2, 1, 'Strawberry', 49.00, 49.00, 59.00, '🥤', 1, 'assets/products/194c7c01-c132-41dd-81ae-1570c0cdb67a_044f75c3.jpg', 'No description'),
(3, 1, 'Cheesecake', 49.00, 49.00, 59.00, '🥤', 1, 'assets/products/aea4e231-73d8-4436-b8d6-55fce079ced7-removebg-preview_be6c8b9d.png', 'No description'),
(4, 1, 'Cookies and Cream', 49.00, 49.00, 59.00, '🥤', 1, 'assets/products/d580bbb3-69ed-4d8b-9743-1951449501d5_4cf331ba.jpg', 'No description'),
(5, 1, 'Java Chips', 49.00, 49.00, 59.00, '🥤', 1, 'assets/products/6719df71-9faa-421d-ae8b-41eb8654ab79_c71e7bf7.jpg', 'No description'),
(6, 1, 'Chocolate', 49.00, 49.00, 59.00, '🥤', 1, 'assets/products/3325bfe8-5c30-4ed6-a0b8-60cb977278fe_df42f889.jpg', 'No description'),
(7, 1, 'Double Dutch', 49.00, 49.00, 59.00, '🥤', 1, 'assets/products/4b955279-1c7d-4b9c-9228-faf384b14911_b15bce36.jpg', 'No description'),
(8, 1, 'Choco Nutella', 49.00, 49.00, 59.00, '🥤', 1, 'assets/products/bc778818-5671-4244-8b39-1a0e5e2e2b63_085c03c9.jpg', 'No description'),
(9, 1, 'Triple Choco', 49.00, 49.00, 59.00, '🥤', 1, 'assets/products/9eac1d0e-3b7e-4d15-87da-31fc31da35c7_1d9559e7.jpg', 'No description'),
(10, 1, 'Avocado', 49.00, 49.00, 59.00, '🥤', 1, 'assets/products/e57668f5-b487-431d-aac6-3603dfbda534_fa89bf98.jpg', 'No description'),
(11, 2, 'Mocha', 49.00, 49.00, 59.00, '☕', 1, 'assets/products/690950651_950321930954483_7580847485942437922_n_d29d9578.jpg', 'No description'),
(12, 2, 'Cappuccino', 49.00, 49.00, 59.00, '☕', 1, 'assets/products/686009709_1505659127898737_1223569342554999227_n_4448bee3.jpg', 'No description'),
(13, 2, 'Caramel Macchiato', 49.00, 49.00, 59.00, '☕', 1, 'assets/products/684400645_1696007901446525_8036324883481442002_n_9662b5b9.jpg', 'No description'),
(14, 3, 'Dark Chocolate', 29.00, 29.00, 39.00, '🧋', 1, 'assets/products/54765772-4557-4bad-b536-4a9bb4ac3c2e_1214a76b.jpg', 'No description'),
(15, 3, 'Chocolate', 29.00, 29.00, 39.00, '🧋', 1, 'assets/products/c88fb4f0-3f91-4eb2-bc5a-32cc28118017_84df4092.jpg', 'No description'),
(16, 3, 'Choco Nutella', 29.00, 29.00, 39.00, '🧋', 1, 'assets/products/bc6c2110-80b5-4278-97bf-e052ec992f67_d34ce1cf.jpg', 'No description'),
(17, 3, 'Cheesecake', 29.00, 29.00, 39.00, '🧋', 1, 'assets/products/d6c721cb-79de-459c-a181-a56f5571ebd1_76b87b36.jpg', 'No description'),
(18, 3, 'Cookies and Cream', 29.00, 29.00, 39.00, '🧋', 1, 'assets/products/d207b06c-0cf8-47de-9912-54794cb57b47_f30eb3eb.jpg', 'No description'),
(19, 3, 'Matcha', 29.00, 29.00, 39.00, '🧋', 1, 'assets/products/b5955471-0668-4efc-a83f-b3c4ef4ae19e_12ef9174.jpg', 'No description'),
(20, 3, 'Strawberry', 29.00, 29.00, 39.00, '🧋', 1, 'assets/products/5b0d8730-5700-49c7-b620-81cde3a9b42d_c4b0b3e5.jpg', 'No description'),
(21, 3, 'Taro', 29.00, 29.00, 39.00, '🧋', 1, 'assets/products/77a8a5f4-98c6-4d60-a44b-696cd7bf68ec_d7d324c7.jpg', 'No description'),
(22, 3, 'Double Dutch', 29.00, 29.00, 39.00, '🧋', 1, 'assets/products/685966138_969766779140003_8246685462897296563_n_395b55e5.jpg', 'No description'),
(23, 3, 'Wintermelon', 29.00, 29.00, 39.00, '🧋', 1, 'assets/products/81f715ce-65d6-431e-84d0-44240d7da476_bd031e58.jpg', 'No description'),
(24, 3, 'Okinawa', 29.00, 29.00, 39.00, '🧋', 1, 'assets/products/d193925e-2969-402c-9fda-b2136793f10e_3f2be535.jpg', 'No description'),
(25, 3, 'Red Velvet', 29.00, 29.00, 39.00, '🧋', 1, 'assets/products/c31e2efa-2f64-43e6-8b7f-1874c88379c8_8f16f669.jpg', 'No description'),
(26, 3, 'Java Chips', 29.00, 29.00, 39.00, '🧋', 1, 'assets/products/687065438_1488960449376641_6478317637308134938_n_b222c80a.jpg', 'No description'),
(27, 3, 'Salted Caramel', 29.00, 29.00, 39.00, '🧋', 1, 'assets/products/686920876_851837120621947_8255620408126127466_n_e7482dd9.jpg', 'No description'),
(29, 3, 'Black Forest', 29.00, 29.00, 39.00, '🧋', 1, 'assets/products/2cab8f29-7a33-4219-9c7e-e6ddabfaa7d8_8d5728e9.jpg', 'No description'),
(30, 4, 'Lemon', 29.00, 29.00, 39.00, '🍋', 1, 'assets/products/2cb60992-99f3-4486-b3f4-a9f690f8c9da_e5f9dabc.jpg', 'No description'),
(31, 4, 'Mango', 29.00, 29.00, 39.00, '🥭', 0, 'assets/products/688607712_1495546958598201_2939607171582053167_n_e2407f52.jpg', 'No description'),
(32, 4, 'Lychee', 29.00, 29.00, 39.00, '🍓', 1, 'assets/products/dbe3dfba-f994-402f-968d-965391698e36_93cc7bd5.jpg', 'No description'),
(35, 4, 'Green Apple', 29.00, 29.00, 39.00, '🍏', 1, 'assets/products/686950103_35408753088771603_1916905608974328173_n_4259127d.jpg', 'No description'),
(36, 4, 'Blueberry', 29.00, 29.00, 39.00, '🫐', 1, 'assets/products/685704677_1454423125884206_2912635038212747783_n_8ffe0616.jpg', 'No description'),
(38, 5, 'Kape Vanilla', 29.00, 29.00, 39.00, '🧊', 1, 'assets/products/f6044dd6-2a48-4189-8872-8d14bb8c0f80-removebg-preview_fce702dd.png', 'No description'),
(39, 5, 'Kape Mocha', 29.00, 29.00, 39.00, '🧊', 1, 'assets/products/687793083_982482840844358_2430219395460562665_n_6740a24e.jpg', 'No description'),
(40, 5, 'Kape Macchiato', 29.00, 29.00, 39.00, '🧊', 1, 'assets/products/693985124_1625481778736957_7377393187195534108_n_7f271788.jpg', 'No description'),
(42, 5, 'Kape Cappuccino', 29.00, 29.00, 39.00, '🧊', 1, 'assets/products/e6e03000-aa41-4f57-8180-384b3adc9521_2026e39f.jpg', 'No description'),
(43, 5, 'Kape Caramel', 29.00, 29.00, 39.00, '🧊', 1, 'assets/products/afb8099e-f7dd-4ab8-8959-f817d7416dac__1_c967d2be.jpg', 'No description'),
(46, 1, 'Mango', 49.00, 49.00, 59.00, '?', 1, 'assets/products/fb0ecd2b-af98-4f42-b908-39747c96b015_df88dc83.jpg', 'No description'),
(47, 5, 'Kape Matcha', 29.00, 29.00, 39.00, '?', 1, 'assets/products/af4f0ed8-f44c-48c1-b778-90e93bbd8f81-removebg-preview_c8336fe6.png', 'No description'),
(48, 4, 'Kiwi', 29.00, 29.00, 39.00, '?', 1, 'assets/products/8958dcee-77ec-404c-95d4-ddb1e3bfa5b6_4b4850ca.jpg', 'No description'),
(49, 4, 'Strawberrry', 29.00, 29.00, 39.00, '?', 1, 'assets/products/687608710_1501771154912727_8945037987014465168_n_b026b4b9.jpg', 'No description'),
(50, 4, 'Honey Peach', 29.00, 29.00, 39.00, '?', 1, 'assets/products/41631d31-6d69-4046-bb60-ca33d691a34e_7eea43f6.jpg', 'No description');

-- --------------------------------------------------------

--
-- Table structure for table `product_inventory`
--

CREATE TABLE `product_inventory` (
  `product_id` int(11) NOT NULL,
  `inventory_id` int(11) NOT NULL,
  `quantity_required` decimal(10,3) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `product_inventory`
--

INSERT INTO `product_inventory` (`product_id`, `inventory_id`, `quantity_required`) VALUES
(1, 7, 0.030),
(1, 8, 0.025),
(1, 42, 1.000),
(1, 43, 1.000),
(1, 44, 1.000),
(2, 7, 0.030),
(2, 9, 0.025),
(2, 42, 1.000),
(2, 43, 1.000),
(2, 44, 1.000),
(3, 7, 0.030),
(3, 10, 0.025),
(3, 42, 1.000),
(3, 43, 1.000),
(3, 44, 1.000),
(4, 7, 0.030),
(4, 11, 0.025),
(4, 42, 1.000),
(4, 43, 1.000),
(4, 44, 1.000),
(5, 7, 0.030),
(5, 12, 0.025),
(5, 42, 1.000),
(5, 43, 1.000),
(5, 44, 1.000),
(6, 7, 0.030),
(6, 13, 0.025),
(6, 42, 1.000),
(6, 43, 1.000),
(6, 44, 1.000),
(7, 7, 0.030),
(7, 14, 0.025),
(7, 42, 1.000),
(7, 43, 1.000),
(7, 44, 1.000),
(8, 7, 0.030),
(8, 42, 1.000),
(8, 43, 1.000),
(8, 44, 1.000),
(9, 7, 0.030),
(9, 16, 0.025),
(9, 42, 1.000),
(9, 43, 1.000),
(9, 44, 1.000),
(10, 7, 0.030),
(10, 17, 0.025),
(10, 42, 1.000),
(10, 43, 1.000),
(10, 44, 1.000),
(11, 7, 0.030),
(11, 18, 0.025),
(11, 37, 0.030),
(11, 42, 1.000),
(11, 43, 1.000),
(11, 44, 1.000),
(12, 7, 0.030),
(12, 19, 0.025),
(12, 37, 0.030),
(12, 42, 1.000),
(12, 43, 1.000),
(12, 44, 1.000),
(13, 7, 0.030),
(13, 20, 0.025),
(13, 37, 0.030),
(13, 42, 1.000),
(13, 43, 1.000),
(13, 44, 1.000),
(14, 7, 0.030),
(14, 21, 0.025),
(14, 42, 1.000),
(14, 43, 1.000),
(14, 44, 1.000),
(15, 7, 0.030),
(15, 13, 0.025),
(15, 42, 1.000),
(15, 43, 1.000),
(15, 44, 1.000),
(16, 7, 0.030),
(16, 42, 1.000),
(16, 43, 1.000),
(16, 44, 1.000),
(17, 7, 0.030),
(17, 10, 0.025),
(17, 42, 1.000),
(17, 43, 1.000),
(17, 44, 1.000),
(18, 7, 0.030),
(18, 11, 0.025),
(18, 42, 1.000),
(18, 43, 1.000),
(18, 44, 1.000),
(19, 7, 0.030),
(19, 22, 0.025),
(19, 42, 1.000),
(19, 43, 1.000),
(19, 44, 1.000),
(20, 7, 0.030),
(20, 9, 0.025),
(20, 42, 1.000),
(20, 43, 1.000),
(20, 44, 1.000),
(21, 7, 0.030),
(21, 8, 0.025),
(21, 42, 1.000),
(21, 43, 1.000),
(21, 44, 1.000),
(22, 7, 0.030),
(22, 14, 0.025),
(22, 42, 1.000),
(22, 43, 1.000),
(22, 44, 1.000),
(23, 7, 0.030),
(23, 23, 0.025),
(23, 42, 1.000),
(23, 43, 1.000),
(23, 44, 1.000),
(24, 7, 0.030),
(24, 24, 0.025),
(24, 42, 1.000),
(24, 43, 1.000),
(24, 44, 1.000),
(25, 7, 0.030),
(25, 25, 0.025),
(25, 42, 1.000),
(25, 43, 1.000),
(25, 44, 1.000),
(26, 7, 0.030),
(26, 12, 0.025),
(26, 42, 1.000),
(26, 43, 1.000),
(26, 44, 1.000),
(27, 7, 0.030),
(27, 42, 1.000),
(27, 43, 1.000),
(27, 44, 1.000),
(28, 7, 0.030),
(28, 42, 1.000),
(28, 43, 1.000),
(28, 44, 1.000),
(29, 7, 0.030),
(29, 28, 0.025),
(29, 42, 1.000),
(29, 43, 1.000),
(29, 44, 1.000),
(30, 7, 0.030),
(30, 29, 0.030),
(30, 42, 1.000),
(30, 43, 1.000),
(30, 44, 1.000),
(31, 7, 0.030),
(31, 30, 0.030),
(31, 42, 1.000),
(31, 43, 1.000),
(31, 44, 1.000),
(32, 7, 0.030),
(32, 31, 0.030),
(32, 42, 1.000),
(32, 43, 1.000),
(32, 44, 1.000),
(35, 7, 0.030),
(35, 33, 0.030),
(35, 42, 1.000),
(35, 43, 1.000),
(35, 44, 1.000),
(36, 7, 0.030),
(36, 34, 0.030),
(36, 42, 1.000),
(36, 43, 1.000),
(36, 44, 1.000),
(38, 7, 0.030),
(38, 36, 0.025),
(38, 37, 0.030),
(38, 42, 1.000),
(38, 43, 1.000),
(38, 44, 1.000),
(39, 7, 0.030),
(39, 18, 0.025),
(39, 37, 0.030),
(39, 42, 1.000),
(39, 43, 1.000),
(39, 44, 1.000),
(40, 7, 0.030),
(40, 20, 0.025),
(40, 37, 0.030),
(40, 42, 1.000),
(40, 43, 1.000),
(40, 44, 1.000),
(42, 7, 0.030),
(42, 19, 0.025),
(42, 37, 0.030),
(42, 42, 1.000),
(42, 43, 1.000),
(42, 44, 1.000),
(43, 7, 0.030),
(43, 37, 0.030),
(43, 42, 1.000),
(43, 43, 1.000),
(43, 44, 1.000);

-- --------------------------------------------------------

--
-- Table structure for table `shop_schedule`
--

CREATE TABLE `shop_schedule` (
  `schedule_id` tinyint(4) NOT NULL,
  `opening_time` time NOT NULL DEFAULT '08:00:00',
  `closing_time` time NOT NULL DEFAULT '23:00:00',
  `shop_status` enum('OPEN','CLOSED') NOT NULL DEFAULT 'CLOSED',
  `last_status_change` datetime DEFAULT NULL,
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `shop_schedule`
--

INSERT INTO `shop_schedule` (`schedule_id`, `opening_time`, `closing_time`, `shop_status`, `last_status_change`, `updated_at`) VALUES
(1, '08:00:00', '23:00:00', 'OPEN', '2026-05-08 08:25:25', '2026-05-08 01:40:47');

-- --------------------------------------------------------

--
-- Table structure for table `users`
--

CREATE TABLE `users` (
  `user_id` int(11) NOT NULL,
  `username` varchar(50) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `role` enum('admin','cashier','customer') NOT NULL DEFAULT 'admin',
  `full_name` varchar(100) NOT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `users`
--

INSERT INTO `users` (`user_id`, `username`, `password_hash`, `role`, `full_name`, `is_active`, `created_at`) VALUES
(1, 'admin', 'ef797c8118f02dfb649607dd5d3f8c7623048c9c063d532cc95c5ed7a898a64f', 'admin', 'Administrator', 1, '2026-05-08 01:40:47'),
(2, 'cashier', 'ef797c8118f02dfb649607dd5d3f8c7623048c9c063d532cc95c5ed7a898a64f', 'cashier', 'Dale', 1, '2026-05-08 01:40:47');

-- --------------------------------------------------------

--
-- Stand-in structure for view `view_daily_sales`
-- (See below for the actual view)
--
CREATE TABLE `view_daily_sales` (
`sales_date` date
,`total_orders` bigint(21)
,`total_sales` decimal(32,2)
,`avg_order_value` decimal(14,6)
);

-- --------------------------------------------------------

--
-- Stand-in structure for view `view_inventory_status`
-- (See below for the actual view)
--
CREATE TABLE `view_inventory_status` (
`inventory_id` int(11)
,`inventory_name` varchar(100)
,`category` varchar(60)
,`unit_name` varchar(30)
,`quantity_on_hand` decimal(10,2)
,`reorder_level` decimal(10,2)
,`stock_status` varchar(20)
,`last_restocked` date
);

-- --------------------------------------------------------

--
-- Stand-in structure for view `view_order_details`
-- (See below for the actual view)
--
CREATE TABLE `view_order_details` (
`order_id` int(11)
,`order_code` varchar(20)
,`full_name` varchar(100)
,`category_name` varchar(80)
,`product_name` varchar(100)
,`size_label` enum('Small','Large')
,`quantity` int(11)
,`unit_price` decimal(10,2)
,`line_total` decimal(10,2)
,`status` enum('Pending','Preparing','Ready','Completed','Cancelled')
,`created_at` timestamp
);

-- --------------------------------------------------------

--
-- Stand-in structure for view `view_product_sales`
-- (See below for the actual view)
--
CREATE TABLE `view_product_sales` (
`product_id` int(11)
,`product_name` varchar(100)
,`category_name` varchar(80)
,`total_qty` decimal(32,0)
,`total_revenue` decimal(32,2)
);

-- --------------------------------------------------------

--
-- Structure for view `view_daily_sales`
--
DROP TABLE IF EXISTS `view_daily_sales`;

CREATE ALGORITHM=UNDEFINED DEFINER=`root`@`localhost` SQL SECURITY DEFINER VIEW `view_daily_sales`  AS SELECT `daily_reports`.`report_date` AS `sales_date`, `daily_reports`.`total_orders` AS `total_orders`, `daily_reports`.`total_sales` AS `total_sales`, case when `daily_reports`.`total_orders` = 0 then 0.00 else round(`daily_reports`.`total_sales` / `daily_reports`.`total_orders`,2) end AS `avg_order_value` FROM `daily_reports` ;

-- --------------------------------------------------------

--
-- Structure for view `view_inventory_status`
--
DROP TABLE IF EXISTS `view_inventory_status`;

CREATE ALGORITHM=UNDEFINED DEFINER=`root`@`localhost` SQL SECURITY DEFINER VIEW `view_inventory_status`  AS SELECT `inventory`.`inventory_id` AS `inventory_id`, `inventory`.`inventory_name` AS `inventory_name`, `inventory`.`category` AS `category`, `inventory`.`unit_name` AS `unit_name`, `inventory`.`quantity_on_hand` AS `quantity_on_hand`, `inventory`.`reorder_level` AS `reorder_level`, `fn_stock_status`(`inventory`.`quantity_on_hand`,`inventory`.`reorder_level`) AS `stock_status`, `inventory`.`last_restocked` AS `last_restocked` FROM `inventory` ;

-- --------------------------------------------------------

--
-- Structure for view `view_order_details`
--
DROP TABLE IF EXISTS `view_order_details`;

CREATE ALGORITHM=UNDEFINED DEFINER=`root`@`localhost` SQL SECURITY DEFINER VIEW `view_order_details`  AS SELECT `o`.`order_id` AS `order_id`, `fn_format_order_code`(`o`.`order_id`) AS `order_code`, coalesce(`u`.`full_name`,`u`.`username`,'Walk-in Customer') AS `full_name`, coalesce(`c`.`category_name`,'Uncategorized') AS `category_name`, coalesce(`p`.`product_name`,'No Product') AS `product_name`, `oi`.`size_label` AS `size_label`, coalesce(`oi`.`quantity`,0) AS `quantity`, coalesce(`oi`.`unit_price`,0.00) AS `unit_price`, coalesce(`oi`.`line_total`,0.00) AS `line_total`, `o`.`status` AS `status`, `o`.`created_at` AS `created_at` FROM ((((`orders` `o` left join `users` `u` on(`u`.`user_id` = `o`.`user_id`)) left join `order_items` `oi` on(`oi`.`order_id` = `o`.`order_id`)) left join `products` `p` on(`p`.`product_id` = `oi`.`product_id`)) left join `categories` `c` on(`c`.`category_id` = `p`.`category_id`)) ;

-- --------------------------------------------------------

--
-- Structure for view `view_product_sales`
--
DROP TABLE IF EXISTS `view_product_sales`;

CREATE ALGORITHM=UNDEFINED DEFINER=`root`@`localhost` SQL SECURITY DEFINER VIEW `view_product_sales`  AS SELECT `p`.`product_id` AS `product_id`, `p`.`product_name` AS `product_name`, `c`.`category_name` AS `category_name`, coalesce(sum(`oi`.`quantity`),0) AS `total_qty`, coalesce(sum(`oi`.`line_total`),0) AS `total_revenue` FROM ((`products` `p` join `categories` `c` on(`c`.`category_id` = `p`.`category_id`)) left join `order_items` `oi` on(`oi`.`product_id` = `p`.`product_id`)) GROUP BY `p`.`product_id`, `p`.`product_name`, `c`.`category_name` ;

--
-- Indexes for dumped tables
--

--
-- Indexes for table `addons`
--
ALTER TABLE `addons`
  ADD PRIMARY KEY (`addon_id`),
  ADD UNIQUE KEY `addon_name` (`addon_name`);

--
-- Indexes for table `categories`
--
ALTER TABLE `categories`
  ADD PRIMARY KEY (`category_id`),
  ADD UNIQUE KEY `category_name` (`category_name`);

--
-- Indexes for table `daily_reports`
--
ALTER TABLE `daily_reports`
  ADD PRIMARY KEY (`report_id`),
  ADD UNIQUE KEY `report_date` (`report_date`);

--
-- Indexes for table `inventory`
--
ALTER TABLE `inventory`
  ADD PRIMARY KEY (`inventory_id`),
  ADD UNIQUE KEY `inventory_name` (`inventory_name`),
  ADD KEY `idx_inventory_category` (`category`);

--
-- Indexes for table `orders`
--
ALTER TABLE `orders`
  ADD PRIMARY KEY (`order_id`),
  ADD KEY `user_id` (`user_id`),
  ADD KEY `idx_orders_created_at` (`created_at`),
  ADD KEY `idx_orders_status` (`status`);

--
-- Indexes for table `order_items`
--
ALTER TABLE `order_items`
  ADD PRIMARY KEY (`order_item_id`),
  ADD KEY `order_id` (`order_id`),
  ADD KEY `product_id` (`product_id`);

--
-- Indexes for table `order_item_addons`
--
ALTER TABLE `order_item_addons`
  ADD PRIMARY KEY (`order_item_addon_id`),
  ADD KEY `order_item_id` (`order_item_id`),
  ADD KEY `addon_id` (`addon_id`);

--
-- Indexes for table `products`
--
ALTER TABLE `products`
  ADD PRIMARY KEY (`product_id`),
  ADD UNIQUE KEY `uq_product_category_name` (`category_id`,`product_name`),
  ADD KEY `idx_products_category` (`category_id`);

--
-- Indexes for table `product_inventory`
--
ALTER TABLE `product_inventory`
  ADD PRIMARY KEY (`product_id`,`inventory_id`),
  ADD KEY `inventory_id` (`inventory_id`);

--
-- Indexes for table `shop_schedule`
--
ALTER TABLE `shop_schedule`
  ADD PRIMARY KEY (`schedule_id`);

--
-- Indexes for table `users`
--
ALTER TABLE `users`
  ADD PRIMARY KEY (`user_id`),
  ADD UNIQUE KEY `username` (`username`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `addons`
--
ALTER TABLE `addons`
  MODIFY `addon_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2289;

--
-- AUTO_INCREMENT for table `categories`
--
ALTER TABLE `categories`
  MODIFY `category_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=9;

--
-- AUTO_INCREMENT for table `daily_reports`
--
ALTER TABLE `daily_reports`
  MODIFY `report_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- AUTO_INCREMENT for table `inventory`
--
ALTER TABLE `inventory`
  MODIFY `inventory_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=44;

--
-- AUTO_INCREMENT for table `orders`
--
ALTER TABLE `orders`
  MODIFY `order_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=3;

--
-- AUTO_INCREMENT for table `order_items`
--
ALTER TABLE `order_items`
  MODIFY `order_item_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=5;

--
-- AUTO_INCREMENT for table `order_item_addons`
--
ALTER TABLE `order_item_addons`
  MODIFY `order_item_addon_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;

--
-- AUTO_INCREMENT for table `products`
--
ALTER TABLE `products`
  MODIFY `product_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=52;

--
-- AUTO_INCREMENT for table `users`
--
ALTER TABLE `users`
  MODIFY `user_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=21263;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `orders`
--
ALTER TABLE `orders`
  ADD CONSTRAINT `orders_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`);

--
-- Constraints for table `order_items`
--
ALTER TABLE `order_items`
  ADD CONSTRAINT `order_items_ibfk_1` FOREIGN KEY (`order_id`) REFERENCES `orders` (`order_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `order_items_ibfk_2` FOREIGN KEY (`product_id`) REFERENCES `products` (`product_id`);

--
-- Constraints for table `order_item_addons`
--
ALTER TABLE `order_item_addons`
  ADD CONSTRAINT `order_item_addons_ibfk_1` FOREIGN KEY (`order_item_id`) REFERENCES `order_items` (`order_item_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `order_item_addons_ibfk_2` FOREIGN KEY (`addon_id`) REFERENCES `addons` (`addon_id`);

--
-- Constraints for table `products`
--
ALTER TABLE `products`
  ADD CONSTRAINT `products_ibfk_1` FOREIGN KEY (`category_id`) REFERENCES `categories` (`category_id`);

--
-- Constraints for table `product_inventory`
--
ALTER TABLE `product_inventory`
  ADD CONSTRAINT `product_inventory_ibfk_1` FOREIGN KEY (`product_id`) REFERENCES `products` (`product_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `product_inventory_ibfk_2` FOREIGN KEY (`inventory_id`) REFERENCES `inventory` (`inventory_id`) ON DELETE CASCADE;

DELIMITER $$
--
-- Events
--
CREATE DEFINER=`root`@`localhost` EVENT `evt_bestbrew_open_shop_daily` ON SCHEDULE EVERY 1 DAY STARTS '2026-05-02 08:00:00' ON COMPLETION NOT PRESERVE ENABLE DO UPDATE shop_schedule
            SET shop_status = 'OPEN',
                last_status_change = NOW()
            WHERE schedule_id = 1$$

CREATE DEFINER=`root`@`localhost` EVENT `evt_bestbrew_close_shop_daily` ON SCHEDULE EVERY 1 DAY STARTS '2026-05-02 23:00:00' ON COMPLETION NOT PRESERVE ENABLE DO UPDATE shop_schedule
            SET shop_status = 'CLOSED',
                last_status_change = NOW()
            WHERE schedule_id = 1$$

DELIMITER ;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
