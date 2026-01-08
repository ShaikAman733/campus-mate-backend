# CampusMate – AI-Powered Institutional Assistant and Student Utility Platform

🔗 Live Application: https://campus-mate-frontend.vercel.app/

---

## Project Overview

CampusMate is a comprehensive web-based platform designed to assist university students through an integrated interface that combines Artificial Intelligence with essential utility services. The system uses a hybrid backend architecture to provide 24/7 assistance, functioning as both an institutional information chatbot and a practical student utility platform.

The goal of CampusMate is to centralize campus-related interactions into a single, responsive web application, reducing dependency on fragmented portals and manual processes.

---

## Problem Statement

Current digital solutions in academic environments often suffer from the following limitations:

- **Static Information Retrieval**  
  Traditional FAQs or rule-based chatbots cannot handle complex or naturally phrased queries.

- **Fragmented Services**  
  Students must navigate multiple portals for profiles, academic queries, and utilities.

- **Lack of Accessibility**  
  Lost-and-found information and campus updates are often limited to physical notice boards.

- **Context Limitation**  
  Generic AI models lack institution-specific knowledge such as faculty details, rules, and schedules.

---

## Solution Description

CampusMate centralizes campus interactions into a single, responsive web application. It employs **Retrieval-Augmented Generation (RAG)** to inject a local institutional knowledge base (JSON data) into the Large Language Model’s context window.

By combining the reasoning capabilities of **Google Gemini (Gemini 2.5 Flash)** with institution-specific data, the system delivers accurate, context-aware responses while preventing AI hallucinations related to campus information.

---

## Key Features

- **RAG-Powered Chatbot**  
  Provides context-aware answers using institution-specific knowledge.

- **Multimodal Interaction**  
  Supports both text and image inputs within the chat interface.

- **Digital Lost and Found**  
  Community-driven module for posting and viewing lost item reports with image support.

- **GPA Calculation Tools**  
  Integrated utility for academic performance tracking.

- **Secure User Management**  
  Authentication, profile management, and role detection (Student vs. Staff).

- **Responsive UI**  
  Single Page Application (SPA) with Dark/Light theme support.

- **Chat History Persistence**  
  Automatically saves and restores previous chat sessions.

---

## Technology Stack

### Frontend
- **React.js** – Builds the responsive Single Page Application
- **Custom Hooks**
  - `useAuth` – Session persistence and authentication state
  - `useChat` – Chat handling and API interaction

### Backend
- **Node.js & Express.js**  
  Primary gateway for authentication, session management, and request proxying.

- **Python & Flask**  
  Microservice for AI processing, RAG logic, and Lost & Found APIs.

- **http-proxy-middleware**  
  Routes AI and utility requests from Node.js to the Python service.

### Database
- **MongoDB Atlas** – Stores users, chat logs, lost items, and knowledge base
- **Mongoose** – Schema management and validation

### AI / Tools
- **Google Gemini API (Gemini 2.5 Flash)** – AI reasoning engine
- **Retrieval-Augmented Generation (RAG)** – Custom keyword-based context retrieval
- **Base64 File Handling** – Image transmission and storage

---

## System Architecture / Workflow

CampusMate follows a **Client–Server–Microservice architecture**:

- **Frontend (React)**  
  Communicates exclusively with the Node.js API (Port 5000).

- **Primary Backend (Node.js Gateway)**  
  Handles authentication, user data, and chat persistence. Proxies AI-related routes (`/chat`, `/api/lostfound`) to the Python service.

- **Secondary Backend (Python AI Service)**  
  Loads the institutional knowledge base into RAM for fast keyword-based searching.

### AI Data Flow
1. User submits a query (text or image)
2. Python service retrieves relevant context using a keyword-scoring algorithm (`deep_search`)
3. Context + query are sent to the Gemini API
4. AI response is returned and streamed to the frontend

---
