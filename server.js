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
 * Prevents the "BOOTING SERVER" loop on the frontend.
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

// Mapping to your existing 'lost_found' collection
const LostFoundSchema = new mongoose.Schema({
  type: { type: String, enum: ['lost', 'found'] },
  item: String,        
  location: String,
  description: String,
  contact: String,     
  image: String,       
  time: { type: String, default: () => new Date().toLocaleString() } 
}, { collection: 'lost_found' }); // Force usage of existing collection

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


app.post('/api/update-profile', async (req, res) => {
  const { username, full_name, department, email, avatar } = req.body;
  try {
    // Find user by username and update their details
    const updatedUser = await User.findOneAndUpdate(
      { username: username }, 
      { 
         // If you want to change the displayed name
        department: department,
        email: email,
        avatar: avatar, // Base64 image string
        updatedAt: Date.now()
      },
      { new: true }
    );

    if (!updatedUser) return res.status(404).json({ error: 'User not found' });
    res.json({ message: 'Profile Updated', user: updatedUser });
  } catch (error) {
    res.status(500).json({ error: 'Update Error' });
  }
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
      const items = await LostFound.find().sort({ _id: -1 }); // Fetches from college_bot
      res.json(items);
    } catch (err) {
      res.status(500).json({ error: "Failed to fetch items" });
    }
});

app.post('/api/lostfound', async (req, res) => {
    try {
      const newItem = new LostFound(req.body);
      await newItem.save();
      res.json({ message: "Reported successfully", item: newItem }); // Return 'item' for UI
    } catch (err) {
      res.status(500).json({ error: "Save failed" });
    }
});

app.delete('/api/lostfound/:id', async (req, res) => {
    try {
        await LostFound.findByIdAndDelete(req.params.id); // Fixes deletion
        res.json({ message: "Item deleted successfully" });
    } catch (err) {
        res.status(500).json({ error: "Delete failed" });
    }
});

app.get('/api/lostfound/image/:id', async (req, res) => {
    try {
        const item = await LostFound.findById(req.params.id);
        if (!item || !item.image) return res.status(404).send('No image');
        const base64Data = item.image.split(",")[1] || item.image;
        const img = Buffer.from(base64Data, 'base64');
        res.writeHead(200, { 'Content-Type': 'image/jpeg', 'Content-Length': img.length });
        res.end(img);
    } catch (err) { res.status(500).send("Error fetching image"); }
});

// --- 9. SERVER START ---
const PORT = process.env.PORT || 10000;
app.listen(PORT, '0.0.0.0', () => {
    console.log(`🚀 NODE: Server is live on port ${PORT}`);
});