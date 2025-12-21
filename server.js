require('dotenv').config();
const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
const bodyParser = require('body-parser');
const { createProxyMiddleware } = require('http-proxy-middleware');

const app = express();

// --- 1. MIDDLEWARE ---
app.use(cors());

// --- 2. PROXY CONFIGURATION ---
// This forwards the /chat and /reload requests to your Python AI service
const pythonUrl = process.env.PYTHON_SERVICE_URL || 'https://campus-bot-python.onrender.com';
console.log(`🌐 Proxy: Forwarding AI traffic to: ${pythonUrl}`);

app.use(createProxyMiddleware({
    target: pythonUrl,
    changeOrigin: true,
    pathFilter: ['/chat', '/reload'], // Proxy only AI-related routes
    onProxyReq: (proxyReq, req, res) => {
        console.log(`📡 PROXY_REQ: [${req.method}] ${req.url}`);
    },
    onProxyRes: (proxyRes, req, res) => {
        console.log(`📡 PROXY_RES: [${proxyRes.statusCode}] from ${req.url}`);
    }
}));

// --- 3. BODY PARSERS ---
app.use(bodyParser.json({ limit: '50mb' })); 
app.use(bodyParser.urlencoded({ limit: '50mb', extended: true }));

// --- 4. MONGODB CONNECTION ---
mongoose.connect(process.env.MONGO_URI)
.then(() => console.log('✅ NODE: MongoDB Connected Successfully'))
.catch(err => console.error('❌ NODE: DB Connection Error:', err));

// --- 5. SCHEMAS & MODELS ---
const UserSchema = new mongoose.Schema({
  username: { type: String, required: true },
  password: { type: String }, 
  email: { type: String, unique: true, sparse: true },
  identifier: String,
  department: String,
  role: { type: String, default: 'Student' },
  avatar: String,
  updatedAt: { type: Date, default: Date.now }
});

const ChatSchema = new mongoose.Schema({
  userId: { type: String, required: true, unique: true },
  sessions: { 
    type: Array, 
    default: [] // Structure: [{ role: "user", parts: ["..."] }, { role: "model", parts: ["..."] }]
  }
});

const User = mongoose.model('User', UserSchema);
const Chat = mongoose.model('Chat', ChatSchema);

// --- 6. AUTH ROUTES ---

app.post('/api/register', async (req, res) => {
  const { username } = req.body;
  try {
    const existingUser = await User.findOne({ username });
    if (existingUser) return res.status(400).json({ error: 'Exists' });

    const newUser = new User({ ...req.body, identifier: username });
    await newUser.save();
    
    // Initialize an empty chat history for the new user
    await new Chat({ userId: newUser._id, sessions: [] }).save();

    res.json({ message: 'Success', user: newUser });
  } catch (error) { 
    res.status(500).json({ error: 'Register Error' }); 
  }
});

app.post('/api/login', async (req, res) => {
  const { username, password } = req.body;
  try {
    const user = await User.findOne({ username, password });
    if (!user) return res.status(401).json({ error: 'Invalid' });
    res.json({ user }); 
  } catch (error) { 
    res.status(500).json({ error: 'Login Error' }); 
  }
});

// --- 7. CHAT HISTORY ROUTES ---

// GET: Retrieve history for a specific user
// ... [Keep your existing imports and Middlewares at the top] ...

// --- 7. CHAT HISTORY ROUTES (UPDATED) ---

// GET: Retrieve history for a specific user
app.get('/api/history/:userId', async (req, res) => {
  try {
    const chatRecord = await Chat.findOne({ userId: req.params.userId });
    res.json(chatRecord ? chatRecord.sessions : []);
  } catch (err) {
    console.error("❌ DB Error during history fetch:", err);
    res.status(500).json({ error: "Server error loading history" });
  }
});

/**
 * FIX 1: ADDED Compatibility Route for /api/save-chat
 * This resolves the 404 error in your browser console.
 * It saves the entire sessions array from React to MongoDB.
 */
app.post('/api/save-chat', async (req, res) => {
  const { userId, sessions } = req.body;
  try {
    if (!sessions) return res.status(400).json({ error: "No session data" });

    const updated = await Chat.findOneAndUpdate(
      { userId },
      { sessions: sessions }, // Overwrites with current UI state
      { upsert: true, new: true }
    );
    res.json({ message: "Full history synced", count: updated.sessions.length });
  } catch (err) {
    console.error("❌ Save-Chat Error:", err);
    res.status(500).json({ error: "Failed to sync full history" });
  }
});

/**
 * FIX 2: IMPROVED Individual Message Update
 * Handles cases where a user might send only an image without text.
 */
app.post('/api/history/update', async (req, res) => {
  const { userId, userMessage, botResponse } = req.body;
  try {
    const updatedChat = await Chat.findOneAndUpdate(
      { userId },
      { 
        $push: { 
          sessions: { 
            $each: [
              { role: "user", parts: [{ text: userMessage || "Sent an attachment" }] },
              { role: "model", parts: [{ text: botResponse }] }
            ] 
          } 
        } 
      },
      { upsert: true, new: true }
    );
    res.json({ status: "Success", historyCount: updatedChat.sessions.length });
  } catch (err) {
    console.error("❌ History Update Error:", err);
    res.status(500).json({ error: "Failed to save turn" });
  }
});

// DELETE: Clear history
app.delete('/api/history/clear/:userId', async (req, res) => {
    try {
        await Chat.findOneAndUpdate({ userId: req.params.userId }, { sessions: [] });
        res.json({ message: "History cleared" });
    } catch (err) {
        res.status(500).json({ error: "Failed to clear history" });
    }
});

// ... [Keep your existing Profile Routes and Server Start code] ...

// --- 8. PROFILE ROUTES ---

app.post('/api/update-profile', async (req, res) => {
  const { username } = req.body;
  try {
    let { email } = req.body;
    if (email === "") email = null;

    const updatedUser = await User.findOneAndUpdate(
      { username }, 
      { ...req.body, email, updatedAt: new Date() },
      { new: true }
    );
    res.status(200).json({ user: updatedUser });
  } catch (error) {
    if (error.code === 11000) return res.status(400).json({ message: "Email in use." });
    res.status(500).json({ message: "Server Error" });
  }
});

// --- 9. SERVER START ---
const PORT = process.env.PORT || 5000;
app.listen(PORT, () => console.log(`🚀 Node Server running on port ${PORT}`));