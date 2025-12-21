require('dotenv').config();
const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
const bodyParser = require('body-parser');
const { createProxyMiddleware } = require('http-proxy-middleware');

const app = express();

// --- 1. MIDDLEWARE ---
app.use(cors());

// --- 2. PROXY CONFIGURATION (STABILIZED) ---
// This handles the routing to your Python backend on Render
const pythonUrl = process.env.PYTHON_SERVICE_URL || 'http://localhost:5001';

// Explicitly mapping routes to prevent 404 errors
app.use(['/chat', '/api/lostfound', '/reload'], createProxyMiddleware({
    target: pythonUrl,
    changeOrigin: true,
    logLevel: 'debug' // This will show detailed logs in Node.js
}));

// --- 3. BODY PARSERS ---
// Must stay AFTER proxy for the chatbot to work
app.use(bodyParser.json({ limit: '50mb' })); 
app.use(bodyParser.urlencoded({ limit: '50mb', extended: true }));

// --- 4. MONGODB ---
mongoose.connect(process.env.MONGO_URI)
.then(() => console.log('✅ MongoDB Connected'))
.catch(err => console.error('❌ MongoDB Error:', err));

// (Your Schemas and Auth Routes remain the same...)

const PORT = process.env.PORT || 5000;
app.listen(PORT, () => console.log(`🚀 Node Server running on port ${PORT}`));