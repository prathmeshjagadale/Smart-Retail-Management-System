# Smart-Retail-Management-System
IoT-Based Smart Retail Management System using ESP32, Three Load Cells, HX711, MQTT, Flask Web Application and SQLite for Real-Time Inventory Monitoring and Automated Billing.
# 🛒 Smart Retail Management System

### IoT-Based Smart Inventory Monitoring and Automated Retail Checkout

An IoT-powered retail automation prototype that integrates smart shelf-weight monitoring, wireless communication, and a web-based application to improve inventory management and simplify the customer checkout process.

---

## 📌 Project Overview

The **Smart Retail Management System** is designed to modernize traditional retail operations using IoT and web technologies.

The system uses three load cells connected to HX711 modules and an ESP32 microcontroller to monitor shelf weight. Sensor readings are transmitted through Wi-Fi using MQTT to a Flask-based web application, where inventory information is displayed and managed.

Customers can browse products, scan QR codes, add products to their cart, complete checkout, and receive an exit verification code.

## 🎯 Objectives

- Automate shelf inventory monitoring using load-cell sensors.
- Enable real-time weight data acquisition and transmission.
- Integrate embedded hardware with a web-based application.
- Provide QR-based product selection and automated billing.
- Support digital checkout and exit-code verification.
- Reduce manual inventory monitoring and checkout effort.

## 🏗️ System Architecture

**Hardware Data Flow:**

Load Cell → HX711 → ESP32 → Wi-Fi → MQTT Broker → Flask Web Application → SQLite Database

**Customer Workflow:**

Product QR Scanning → Shopping Cart → Billing → Payment → Exit Code Generation → Cashier Verification

## ⚙️ Hardware Components

| Component | Quantity | Purpose |
|---|---:|---|
| ESP32 | 1 | Microcontroller and Wi-Fi communication |
| Load Cell | 3 | Shelf-weight measurement |
| HX711 | 3 | Load-cell signal interfacing |
| Power supply | As required | Hardware operation |
| Connecting wires | As required | Circuit connections |

## 💻 Software and Technologies

- **Embedded Programming:** ESP32 firmware
- **Programming Language:** Python
- **Backend Framework:** Flask
- **Communication Protocol:** MQTT
- **MQTT Broker:** HiveMQ
- **Database:** SQLite
- **Frontend:** Web technologies
- **QR Code:** QR-based product identification
- **Payment:** Razorpay test mode / simulated payment fallback

## 🚀 Key Features

### 1. Smart Inventory Monitoring
- Three load-cell channels for shelf-weight measurement.
- Real-time sensor data transmission.
- Weight-based stock quantity estimation.
- Inventory monitoring through an administrative dashboard.

### 2. IoT Communication
- ESP32-based sensor data acquisition.
- Wi-Fi connectivity.
- MQTT-based wireless communication.
- Integration between hardware and web application.

### 3. Customer Shopping Interface
- Product browsing and QR-code scanning.
- Digital shopping cart.
- Automatic bill calculation.
- Checkout workflow.

### 4. Payment and Exit Verification
- Payment workflow with test-mode or simulated-payment support.
- Unique exit-code generation after successful checkout.
- Cashier-side exit-code verification.

### 5. Administration
- Product and inventory management.
- Customer and cashier interfaces.
- Sales and order information.
- Inventory monitoring and reporting.

## 🔄 Working Principle

1. Load cells measure the weight of products placed on the shelves.
2. HX711 modules interface the load cells with the ESP32.
3. ESP32 collects sensor readings and transmits them through MQTT over Wi-Fi.
4. The Flask application receives and processes the readings.
5. Inventory information is stored and managed using SQLite.
6. Customers select products using the QR-based interface.
7. The application calculates the bill and processes the checkout workflow.
8. An exit code is generated after successful checkout and verified by the cashier.

## 📂 Project Structure

The repository contains the embedded firmware, web application, database-related files, and project documentation. Refer to the actual folders and source files uploaded to this repository.

## 🔧 Installation and Execution

The exact installation commands and execution steps depend on the included project structure.

1. Clone this repository.
2. Install the required Python dependencies.
3. Configure the Flask application and SQLite database.
4. Configure ESP32 Wi-Fi and MQTT settings.
5. Upload the firmware to the ESP32.
6. Start the Flask web application.
7. Open the application in a web browser and test the hardware integration.

Refer to the source code and configuration files for the exact setup requirements.

## 🔮 Future Scope

- Integration with 5G connectivity.
- Advanced inventory analytics and demand forecasting.
- Enhanced payment gateway integration.
- Improved retail security and transaction monitoring.
- Scalability for multiple retail shelves and stores.

## ⚠️ Project Scope and Notes

This is a working prototype demonstrating IoT-based inventory monitoring and a software-based checkout workflow. The current hardware communication uses Wi-Fi and MQTT. QR codes are used for configured product identification, not computer-vision recognition. Payment simulation, if used, should not be interpreted as a live financial transaction.

## 👨‍💻 Project Category

**Final-Year Mega Project | Internet of Things | Embedded Systems | Web Development | Retail Automation**

---

**Developed by:** Prathmesh Jagadale

**GitHub:** https://github.com/prathmeshjagadale

