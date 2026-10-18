-- Project Atlas: MySQL Database Initialization & Seed Script
-- Cognitive Market Research and Consulting (CMR)

CREATE DATABASE IF NOT EXISTS `project_atlas` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `project_atlas`;

-- 1. Reports Master Table
DROP TABLE IF EXISTS `market_metrics`;
DROP TABLE IF EXISTS `escalations`;
DROP TABLE IF EXISTS `feedback`;
DROP TABLE IF EXISTS `conversations`;
DROP TABLE IF EXISTS `audit_logs`;
DROP TABLE IF EXISTS `clients`;
DROP TABLE IF EXISTS `reports`;

CREATE TABLE `reports` (
    `id` VARCHAR(20) NOT NULL PRIMARY KEY,
    `title` VARCHAR(255) NOT NULL,
    `publisher` VARCHAR(100) NOT NULL,
    `published` DATE NOT NULL,
    `sector` VARCHAR(100) NOT NULL,
    `access` VARCHAR(50) NOT NULL -- 'paid' or 'public excerpt'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. Market Metrics Table
CREATE TABLE `market_metrics` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `report` VARCHAR(20) NOT NULL,
    `metric` VARCHAR(100) NOT NULL,
    `region` VARCHAR(50) NOT NULL,
    `year_period` VARCHAR(50) NOT NULL,
    `value` VARCHAR(100) NOT NULL,
    `scope_note` TEXT NOT NULL,
    FOREIGN KEY (`report`) REFERENCES `reports`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. Clients Table (Confidential Email)
CREATE TABLE `clients` (
    `id` VARCHAR(20) NOT NULL PRIMARY KEY,
    `company` VARCHAR(100) NOT NULL,
    `contact_email` VARCHAR(100) NOT NULL, -- Confidential client information
    `purchased_reports` TEXT NOT NULL -- Comma separated report IDs
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. Human-in-the-loop Escalations Table
CREATE TABLE `escalations` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `client_id` VARCHAR(20) NOT NULL,
    `question` TEXT NOT NULL,
    `reason` VARCHAR(255) NOT NULL,
    `confidence` FLOAT NOT NULL,
    `status` VARCHAR(50) NOT NULL DEFAULT 'pending', -- 'pending', 'resolved', 'closed'
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5. Chat History / Conversations Table
CREATE TABLE `conversations` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `session_id` VARCHAR(100) NOT NULL,
    `client_id` VARCHAR(20) NOT NULL,
    `question` TEXT NOT NULL,
    `answer` LONGTEXT NOT NULL,
    `citations` JSON NULL,
    `conflicts` JSON NULL,
    `derived_values` JSON NULL,
    `confidence` FLOAT NOT NULL,
    `escalated` TINYINT(1) NOT NULL DEFAULT 0,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 6. User Feedback Table (Thumbs Up / Thumbs Down)
CREATE TABLE `feedback` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `conversation_id` INT NOT NULL,
    `rating` ENUM('up', 'down') NOT NULL,
    `comments` TEXT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`conversation_id`) REFERENCES `conversations`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 7. Audit & Security Log Table
CREATE TABLE `audit_logs` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `event_type` VARCHAR(50) NOT NULL, -- 'injection_attempt', 'sql_blocked', 'sql_executed', 'entitlement_blocked', 'request'
    `client_id` VARCHAR(20) NULL,
    `query_text` TEXT NULL,
    `details` JSON NULL,
    `latency_ms` FLOAT NULL,
    `cost_usd` FLOAT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ==========================================================
-- SEED DATA
-- ==========================================================

-- Reports Seed
INSERT INTO `reports` (`id`, `title`, `publisher`, `published`, `sector`, `access`) VALUES
('R-101', 'Global Smart Water Meter Market 2025', 'CMR', '2025-03-10', 'Utilities', 'paid'),
('R-102', 'Smart Water Metering: Industry Outlook 2024', 'Aquila Insights (third party)', '2024-06-18', 'Utilities', 'public excerpt'),
('R-103', 'Residential Water Purifier Market 2025', 'CMR', '2025-01-22', 'Consumer Durables', 'paid'),
('R-104', 'Commercial Heat Pumps Market 2025', 'CMR', '2025-02-14', 'Clean Energy', 'paid'),
('R-105', 'EV Fast Charging Infrastructure 2025', 'CMR', '2025-02-28', 'Automotive', 'paid'),
('R-106', 'Industrial IoT Sensors Market 2025', 'CMR', '2025-04-05', 'Manufacturing', 'paid'),
('R-107', 'Smart Grid Distribution Automation 2024', 'GridVision Research (third party)', '2024-11-15', 'Utilities', 'public excerpt');

-- Market Metrics Seed
INSERT INTO `market_metrics` (`report`, `metric`, `region`, `year_period`, `value`, `scope_note`) VALUES
('R-101', 'Market size', 'Global', '2024', 'USD 4.21 B', 'Includes hardware, software and services'),
('R-101', 'CAGR', 'Global', '2025-2030', '11.2 %', 'Forecast period stated as 2025-2030'),
('R-101', 'Regional share', 'APAC', '2024', '38 %', 'Share of global market size'),

('R-102', 'Market size', 'Global', '2024', 'USD 3.87 B', 'AMR / AMI hardware only'),
('R-102', 'CAGR', 'Global', '2024-2029', '9.8 %', 'Different forecast window from R-101'),
('R-102', 'Regional share', 'APAC', '2024', '41 %', 'Share of hardware market'),

('R-103', 'Market size', 'Global', '2024', 'USD 9.60 B', 'Point-of-use residential purification systems'),
('R-103', 'CAGR', 'Global', '2025-2030', '8.5 %', 'Forecast period stated as 2025-2030'),
('R-103', 'Regional share', 'APAC', '2024', '46 %', 'Share of global consumer durables water filtration'),

('R-104', 'Market size', 'Global', '2024', 'USD 8.12 B', 'Air-to-water & ground-source commercial installations'),
('R-104', 'CAGR', 'Global', '2025-2030', '13.4 %', 'Forecast period stated as 2025-2030'),
('R-104', 'Regional share', 'Europe', '2024', '44 %', 'Driven by EU decarbonization policy'),

('R-105', 'Market size', 'Global', '2024', 'USD 5.75 B', 'DC fast charging equipment and cloud network software'),
('R-105', 'CAGR', 'Global', '2025-2030', '22.8 %', 'Forecast period stated as 2025-2030'),
('R-105', 'Regional share', 'APAC', '2024', '52 %', 'High growth segment led by China and Korea'),

('R-106', 'Market size', 'Global', '2024', 'USD 12.30 B', 'Vibration, temperature, acoustic and pressure industrial sensors'),
('R-106', 'CAGR', 'Global', '2025-2030', '10.1 %', 'Forecast period stated as 2025-2030'),
('R-106', 'Regional share', 'North America', '2024', '36 %', 'Industry 4.0 predictive maintenance installations'),

('R-107', 'Market size', 'Global', '2024', 'USD 7.40 B', 'Substation automation and feeder management hardware'),
('R-107', 'CAGR', 'Global', '2024-2029', '7.9 %', 'Forecast period stated as 2024-2029'),
('R-107', 'Regional share', 'North America', '2024', '40 %', 'Grid modernization utility programs');

-- Clients Seed (Confidential Data)
INSERT INTO `clients` (`id`, `company`, `contact_email`, `purchased_reports`) VALUES
('C-01', 'Northwind Utilities', 'ops@example.com', 'R-101, R-103'),
('C-02', 'Blue Delta Infra', 'procurement@example.com', 'R-103');

-- Read-only DB User Configuration (for SQL tool safety)
-- Creates a dedicated restricted user that can ONLY perform SELECT queries
CREATE USER IF NOT EXISTS 'atlas_readonly'@'%' IDENTIFIED BY 'AtlasReadOnly_Pass2025!';
GRANT SELECT ON `project_atlas`.* TO 'atlas_readonly'@'%';
FLUSH PRIVILEGES;
