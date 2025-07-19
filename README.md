

**Team Name** : Byteforce
---
**Team Leader's Name** : Bhoomika Surve
---
**Team Members’ Names** : Jatush Hingu, Shreel Thakur, Priyanka Bhandari
---
**Selected Domain**: Healthcare
---
**Problem Statement** : HC-01:Problem Statement
Essential medicines such as insulin and thyroid medications frequently go out of
stock without prior warning, especially at the district level. This leads to public
panic, price gouging, and black-market hoarding, with no centralized mechanism
to detect or act on such shortages in real time.
---
# 🏥 Medicine Supply Chain Platform using Blockchain & AI

An integrated **Web3 + AI Healthcare System** built with **Flask**, **Ethereum Blockchain**, and **Machine Learning**. The platform offers transparent medicine inventory management, shortage predictions, auto-ordering, and patient-powered reporting — all connected via a secure blockchain backend and real-time dashboards.

---

## 📸 UI Screenshots

| Feature                               | Screenshot          |
|---------------------------------------|---------------------|
| 🌐 Landing Page                       | `index1.png`        |
| 🧾 Blockchain Logs                    | `BC1.png`, `BC2.png`|
| 🧠 ML Shortage Prediction             | `predict_medi.png`  |
| 💊 Alternative Medicine Suggestion   | `alternatemedi.png` |
| 📍 Pharmacy Locator with Maps         | `pharmacylocator.png` |
| 🚨 Shortage Reporting                 | `shortage.png`      |
| 📦 Inventory Management & Dashboard  | `index2.png`, `index3.png` |
| ⚙️ Backend Design                     | `base1.png`, `base2.png` |

---

## 🚀 Key Features

### 🔗 Blockchain-Powered Inventory System
- Logs **medicine stock updates**, **shortage reports**, and **auto-manufacturer orders** on Ethereum.
- Real-time blockchain dashboard (`BC1.png`, `BC2.png`).
- Smart contracts automatically trigger orders when stock < 20%.

### 📦 Pharmacy Inventory Management
- Track medicine batches, expiry dates, and pricing.
- Minimum stock alert system integrated with blockchain.
- Dashboards and alerts shown in `index2.png`, `index3.png`.

### 🧠 AI/ML-Based Prediction Engine
- Predicts **medicine shortages** and **price spikes** using regional, seasonal, and demand data.
- Built with scikit-learn and custom feature engineering.
- UI shown in `predict_medi.png`.

### 💊 Alternative Medicine Recommendations
- Suggests substitutes using **TF-IDF** and **cosine similarity** on medicine composition.
- UI shown in `alternatemedi.png`.

### 📍 Nearby Pharmacy Locator
- Shows pharmacies with specific medicines within user-defined radius.
- Uses Haversine formula for distance, maps powered by Leaflet.
- UI: `pharmacylocator.png`.

### 🧾 Patient-Powered Shortage Reports
- Patients report unavailable, fake, or overpriced medicines.
- Upload prescriptions and location.
- Reports aggregated into active shortage alerts (`shortage.png`).

### 📊 Admin & Authority Dashboards
- Analytics on affected locations, top shortages, and demand surges.
- System-wide configuration via admin routes.

---

## 🛠️ Tech Stack

| Layer       | Technologies                            |
|-------------|-----------------------------------------|
| Backend     | Flask, Python, SQLite                   |
| Blockchain  | Ethereum, Solidity, Hardhat, Web3.py    |
| Machine Learning | Scikit-learn, Joblib, Pandas       |
| Frontend    | HTML, Jinja2, Bootstrap, JavaScript     |
| Geolocation | Leaflet.js, Geopy                       |

---

## 🧾 Database Schema

This app uses `database.db` as the unified database for predictions, inventory, pharmacy, and reporting.

### `users`
Stores all user accounts (patients, pharmacies, admins, authorities).

| Field          | Type     | Description                     |
|----------------|----------|---------------------------------|
| id             | INTEGER  | Primary key                     |
| username       | TEXT     | Unique login                    |
| email          | TEXT     | Unique email                    |
| password_hash  | TEXT     | Hashed password                 |
| user_type      | TEXT     | Role: admin, pharmacy, patient  |
| is_verified    | BOOLEAN  | Account status                  |

---

### `pharmacies`
Registered pharmacy details and geo-coordinates.

| Field            | Type     | Description                     |
|------------------|----------|---------------------------------|
| id               | INTEGER  | Primary key                     |
| user_id          | INTEGER  | FK to users                     |
| pharmacy_name    | TEXT     | Name of pharmacy                |
| license_number   | TEXT     | Unique license ID               |
| location_id      | INTEGER  | Location FK                     |
| latitude         | DECIMAL  | Geo                             |
| longitude        | DECIMAL  | Geo                             |

---

### `pharmacy_inventory`
Medicine stock per pharmacy.

| Field               | Type     | Description                  |
|---------------------|----------|------------------------------|
| pharmacy_id         | INTEGER  | FK to pharmacy               |
| medicine_id         | INTEGER  | FK to medicines              |
| current_stock       | INTEGER  | In-stock quantity            |
| unit_price          | DECIMAL  | Selling price                |
| mrp                 | DECIMAL  | Maximum Retail Price         |
| batch_number        | TEXT     | Batch reference              |
| expiry_date         | DATE     | Expiry                       |
| minimum_stock_level | INTEGER  | Alert threshold              |

---

### `medicines`
Master medicine table.

| Field         | Type    | Description                      |
|---------------|---------|----------------------------------|
| id            | INTEGER | Primary key                      |
| name          | TEXT    | Commercial name                  |
| generic_name  | TEXT    | Generic name                     |
| category      | TEXT    | Classification                  |
| manufacturer  | TEXT    | Brand/manufacturer               |

---

### `manufacturer_orders`
Smart contract-based manufacturer orders.

| Field                | Type     | Description                       |
|----------------------|----------|-----------------------------------|
| blockchain_order_id  | TEXT     | Unique TX hash                    |
| medicine_id          | INTEGER  | FK to medicine                    |
| quantity_ordered     | INTEGER  | How much to restock               |
| retailer_address     | TEXT     | Ethereum address of pharmacy      |
| status               | TEXT     | `pending`, `confirmed`, `shipped` |

---

### `patient_reports`
Crowdsourced data from patients.

| Field         | Type     | Description                       |
|---------------|----------|-----------------------------------|
| user_id       | INTEGER  | Patient reporting                 |
| medicine_id   | INTEGER  | Affected medicine                 |
| location_id   | INTEGER  | Where shortage was observed       |
| report_type   | TEXT     | `shortage`, `overpriced`, etc.    |
| description   | TEXT     | User-submitted notes              |

---

### `shortage_alerts`, `price_history`, `locations`, `notifications`, `system_settings`
Support analytics, history logging, user alerts, and config settings.

---

## 🧠 AI/ML Model Details

- Data source: `pharmacy_medicines` table (price, availability, demand)
- Features used:
  - Season
  - Location
  - Medicine ID
  - Demand percentage
- Output: Prediction of **shortage** and **price hike risk**

---
