# BIS Sahayta — Frontend

> A modern, accessible frontend for **BIS Sahayta**, an AI-powered assistant for information related to the Bureau of Indian Standards (BIS).

BIS Sahayta provides a simple conversational interface for users to ask questions, explore BIS-related information, and receive guided assistance through an intuitive **Guide Me** workflow.

---

## ✨ Features

* 💬 **AI Chat Interface**

  * Ask questions in a conversational interface.
  * Connects to the BIS Sahayta backend through REST APIs.
  * Displays AI-generated responses and source information.

* 🧭 **Guide Me**

  * Step-by-step guided questionnaire.
  * Helps users identify what they need.
  * Generates a structured guidance report.
  * Allows users to continue the conversation after completing the guide.

* 🔎 **Search**

  * Search interface for navigating the assistant experience.

* 🕘 **Chat History**

  * Interface for managing previous conversations.

* 📎 **Attachment Interface**

  * UI support for attaching files to conversations.

* 🎙️ **Voice Interaction UI**

  * Microphone interaction for future voice-based functionality.

* 🌗 **Dark / Light Mode**

  * Switch between dark and light themes.

* 📱 **Responsive Design**

  * Designed to work across desktop and smaller screens.

* ♿ **User-Friendly UX**

  * Designed with non-technical users in mind.
  * Clear navigation and simple interaction patterns.

---

## 🛠️ Tech Stack

### Frontend

* **React.js**
* **Vite**
* **JavaScript (ES6+)**
* **CSS3**
* **Lucide React** — icons
* **REST API** — backend communication

### Backend Integration

The frontend communicates with the BIS Sahayta backend through the `/api/chat` endpoint.

The backend is expected to run locally on:

```text
http://localhost:8000
```

---

## 📁 Project Structure

```text
BIS-Sahayta-Frontend/
│
├── src/
│   ├── assets/
│   │   └── bis.png
│   │
│   ├── main.jsx
│   └── styles.css
│
├── index.html
├── package.json
├── package-lock.json
├── vite.config.js
├── .gitignore
└── README.md
```

---

# 🚀 Getting Started

## 1. Prerequisites

Make sure you have installed:

* **Node.js** — preferably Node.js 18+
* **npm**
* **Git**

Check your versions:

```bash
node --version
npm --version
git --version
```

---

## 2. Clone the Repository

```bash
git clone https://github.com/masooma-12/BIS-Sahayta-Frontend.git
```

Move into the project:

```bash
cd BIS-Sahayta-Frontend
```

---

## 3. Install Dependencies

Run:

```bash
npm install
```

This installs all required frontend packages.

---

## 4. Start the Development Server

Run:

```bash
npm run dev
```

Vite will start the development server.

You should see something similar to:

```text
Local: http://localhost:5173/
```

Open the displayed URL in your browser.

---

# 🔌 Backend Connection

The frontend is designed to communicate with the BIS Sahayta backend.

The expected backend address is:

```text
http://localhost:8000
```

The frontend sends chat requests to:

```text
POST /api/chat
```

The request contains information such as:

```json
{
  "query": "What are BIS standards?",
  "lang": "en",
  "top_k": 5
}
```

The backend should return the generated answer along with relevant information such as sources and confidence where available.

---

## 🖥️ Running Frontend + Backend Together

You need **two terminals**.

### Terminal 1 — Backend

Start the BIS Sahayta backend:

```bash
uvicorn app.main:app --reload --port 8000
```

The backend should then be available at:

```text
http://localhost:8000
```

### Terminal 2 — Frontend

From the frontend directory:

```bash
npm install
npm run dev
```

The frontend will normally be available at:

```text
http://localhost:5173
```

---

# 🔄 Application Flow

```text
                ┌─────────────────┐
                │   BIS Sahayta   │
                │    Frontend     │
                └────────┬────────┘
                         │
             ┌───────────┴───────────┐
             │                       │
          Chat UI                Guide Me
             │                       │
             │                 User Questions
             │                       │
             └───────────┬───────────┘
                         │
                         ▼
                  /api/chat
                         │
                         ▼
                ┌─────────────────┐
                │ BIS Sahayta API │
                │    Backend      │
                └────────┬────────┘
                         │
                         ▼
                AI / RAG Processing
                         │
                         ▼
                  Answer + Sources
                         │
                         ▼
                ┌─────────────────┐
                │   Chat Interface│
                └─────────────────┘
```

---

# 🧭 Guide Me Flow

The **Guide Me** feature uses a four-step questionnaire.

```text
Start
  │
  ▼
What do you need help with?
  │
  ▼
What product/service is involved?
  │
  ▼
What information do you need?
  │
  ▼
What would you like to do next?
  │
  ▼
Generate Report
  │
  ▼
Structured Guidance
  │
  ▼
Continue to Chat
```

The generated report summarizes the user's answers and provides a recommended action path.

---

# 🎨 UI / UX

The interface focuses on:

* Clear visual hierarchy
* Simple navigation
* Conversational interaction
* Accessible controls
* Responsive layouts
* Dark and light themes
* BIS branding
* Minimal cognitive load for non-technical users

The frontend uses the official BIS logo within the application branding.

---

# 🔐 API Authentication

The current frontend sends an API key with chat requests:

```text
X-API-Key: demo-key-123
```

This value is intended for the current development setup.

For production deployment, authentication and API credentials should be handled through appropriate environment/configuration mechanisms rather than exposing development credentials in frontend source code.

---

# 🧪 Development

After making changes to the source files, Vite automatically reloads the application during development.

Main frontend files:

```text
src/main.jsx
src/styles.css
```

For a production build:

```bash
npm run build
```

To preview the production build locally:

```bash
npm run preview
```

---

# 📦 Production Build

Create the optimized production build:

```bash
npm run build
```

The generated files will be placed inside:

```text
dist/
```

The `dist` directory can then be deployed to a suitable static hosting platform.

---

# 🐛 Troubleshooting

### `npm run dev` doesn't work

Make sure you are inside the frontend directory:

```bash
cd BIS-Sahayta-Frontend
```

Then run:

```bash
npm install
npm run dev
```

---

### Backend connection error

If the UI shows that it cannot connect to the BIS backend, make sure the backend is running on:

```text
http://localhost:8000
```

You can start it with:

```bash
uvicorn app.main:app --reload --port 8000
```

---

### Port 5173 is already in use

Vite may automatically select another available port.

Check the terminal output for the actual URL.

---

### Dependencies are broken

Try reinstalling them:

```bash
rm -rf node_modules package-lock.json
npm install
```

On Windows PowerShell:

```powershell
Remove-Item -Recurse -Force node_modules
Remove-Item package-lock.json
npm install
```

---

# 👩‍💻 Development

This repository contains the **frontend implementation** of BIS Sahayta.

The frontend is developed using React + Vite and is designed to integrate with the BIS Sahayta backend services through REST APIs.

---

## 📌 Project Status

**Frontend:** 🚧 Active Development

Current frontend capabilities include:

* Chat interface
* BIS branding
* Guide Me workflow
* Structured guidance report
* Dark/light theme
* Responsive UI
* Backend API integration

---

## 📄 License

This project is currently intended for educational, development, and project purposes.

---

## 🙌 Acknowledgements

Built as part of the development of **BIS Sahayta**, with the goal of making BIS-related information easier to access through an intuitive AI-assisted interface.
