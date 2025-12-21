require('dotenv').config();
const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
const bodyParser = require('body-parser');
const { createProxyMiddleware } = require('http-proxy-middleware');

const app = express();

// --- 1. MIDDLEWARE ---
app.use(cors());

/**
 * HEALTH CHECK ROUTE
 * Prevents the "Booting Server" loop on the frontend.
 */
app.get('/', (req, res) => {
    res.status(200).send("Campus Mate Node Server is Running 🚀");
});

// --- 2. PROXY CONFIGURATION ---
const pythonUrl = process.env.PYTHON_SERVICE_URL || 'https://campus-bot-python.onrender.com';

app.use(createProxyMiddleware({
    target: pythonUrl,
    changeOrigin: true,
    pathFilter: ['/chat', '/reload'], 
    onProxyReq: (proxyReq, req, res) => {
        console.log(`📡 PROXY_REQ: [${req.method}] ${req.url}`);
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
  sessions: { type: Array, default: [] }
});

// UPDATED: Matches your existing 'lost_found' collection structure
const LostFoundSchema = new mongoose.Schema({
  type: { type: String, enum: ['lost', 'found'] },
  item: String,        // Changed from 'title' to 'item' to match Compass
  location: String,
  description: String,
  contact: String,     // Added to match Compass
  image: String,       // Added to match Compass
  time: { type: String, default: () => new Date().toLocaleString() } // Matches your string format
}, { collection: 'lost_found' }); // FORCES Mongoose to use your existing collection

const User = mongoose.model('User', UserSchema);
const Chat = mongoose.model('Chat', ChatSchema);
const LostFound = mongoose.model('LostFound', LostFoundSchema);

// --- 6. AUTH ROUTES ---

app.post('/api/register', async (req, res) => {
  const { username } = req.body;
  try {
    const existingUser = await User.findOne({ username });
    if (existingUser) return res.status(400).json({ error: 'Exists' });
    const newUser = new User({ ...req.body, identifier: username });
    await newUser.save();
    await new Chat({ userId: newUser._id, sessions: [] }).save();
    res.json({ message: 'Success', user: newUser });
  } catch (error) { res.status(500).json({ error: 'Register Error' }); }
});

app.post('/api/login', async (req, res) => {
  const { username, password } = req.body;
  try {
    const user = await User.findOne({ username, password });
    if (!user) return res.status(401).json({ error: 'Invalid' });
    res.json({ user }); 
  } catch (error) { res.status(500).json({ error: 'Login Error' }); }
});

// --- 7. CHAT HISTORY ROUTES ---

app.get('/api/history/:userId', async (req, res) => {
  try {
    const chatRecord = await Chat.findOne({ userId: req.params.userId });
    res.json(chatRecord ? chatRecord.sessions : []);
  } catch (err) { res.status(500).json({ error: "Server error" }); }
});

app.post('/api/save-chat', async (req, res) => {
  const { userId, sessions } = req.body;
  try {
    const updated = await Chat.findOneAndUpdate({ userId }, { sessions }, { upsert: true, new: true });
    res.json({ message: "Synced", count: updated.sessions.length });
  } catch (err) { res.status(500).json({ error: "Sync failed" }); }
});

// --- 8. LOST & FOUND ROUTES ---

app.get('/api/lostfound', async (req, res) => {
    try {
      // Fetches existing data from 'lost_found' collection
      const items = await LostFound.find().sort({ _id: -1 });
      res.json(items);
    } catch (err) {
      res.status(500).json({ error: "Failed to fetch" });
    }
});

app.post('/api/lostfound', async (req, res) => {
    try {
      const newItem = new LostFound(req.body);
      await newItem.save();
      res.json({ message: "Reported successfully", item: newItem });
    } catch (err) {
      res.status(500).json({ error: "Save failed" });
    }
});

// --- 9. SERVER START ---
const PORT = process.env.PORT || 10000;
app.listen(PORT, '0.0.0.0', () => {
    console.log(`🚀 NODE: Server live on port ${PORT}`);
});