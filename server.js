require('dotenv').config();
const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
const bodyParser = require('body-parser');
const { createProxyMiddleware } = require('http-proxy-middleware');

const app = express();

// --- 1. MIDDLEWARE ---
app.use(cors());

// --- 2. PROXY CONFIGURATION (MOVED UP) ---
// CRITICAL: This must come BEFORE bodyParser so the request stream isn't consumed
// This fixes the "Chatbot not responding" issue.
app.use(createProxyMiddleware({
    target: 'http://localhost:5001',
    changeOrigin: true,
    pathFilter: ['/chat', '/api/lostfound', '/reload'] 
}));

// --- 3. BODY PARSERS (MOVED DOWN) ---
// Increased limit to 50mb to handle both Chat images and Profile Avatars
app.use(bodyParser.json({ limit: '50mb' })); 
app.use(bodyParser.urlencoded({ limit: '50mb', extended: true }));

// --- 4. MONGODB CONNECTION ---
const mongoURI = process.env.MONGO_URI;

mongoose.connect(mongoURI)
.then(() => console.log('✅ MongoDB Atlas Connected Successfully'))
.catch(err => console.error('❌ MongoDB Connection Error:', err));

// --- 5. SCHEMAS ---

// User Schema
const UserSchema = new mongoose.Schema({
  username: { type: String, required: true }, // Used for Login (USN or Custom Name)
  password: { type: String }, 
  
  // Profile Details
  email: { type: String, unique: true, sparse: true }, // sparse allows nulls (but not empty strings)
  isNewAdmission: Boolean,
  identifier: String, // Display Name / USN in Profile
  department: String,
  role: String,
  avatar: String, // Base64 string
  updatedAt: { type: Date, default: Date.now }
});

const ChatSchema = new mongoose.Schema({
  userId: { type: String, required: true },
  sessions: { type: Array, default: [] }
});

const User = mongoose.model('User', UserSchema);
const Chat = mongoose.model('Chat', ChatSchema);

// --- 6. ROUTES ---

// Auth: Register
app.post('/api/register', async (req, res) => {
  const { username, password } = req.body;
  try {
    const existingUser = await User.findOne({ username });
    if (existingUser) return res.status(400).json({ error: 'Username/USN already exists' });

    // Create new user with default profile values
    const newUser = new User({ 
      username, 
      password,
      identifier: username, // Default identifier to the username/USN provided
      role: 'Student',
      isNewAdmission: !username.toUpperCase().startsWith('1RL') // Auto-detect if not USN
    });
    await newUser.save();
    
    // Initialize Chat
    const newChat = new Chat({ userId: newUser._id, sessions: [] });
    await newChat.save();

    res.json({ message: 'Registration successful', user: newUser });
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: 'Error registering user' });
  }
});

// Auth: Login
app.post('/api/login', async (req, res) => {
  const { username, password } = req.body;
  try {
    const user = await User.findOne({ username, password });
    if (!user) return res.status(401).json({ error: 'Invalid credentials' });

    // Return the FULL user object (including avatar, dept, etc.)
    res.json({ user: user }); 
  } catch (error) {
    res.status(500).json({ error: 'Error logging in' });
  }
});

// Chat: Save History
app.post('/api/save-chat', async (req, res) => {
  const { userId, sessions } = req.body;
  try {
    await Chat.findOneAndUpdate({ userId }, { sessions }, { upsert: true });
    res.json({ success: true });
  } catch (error) {
    res.status(500).json({ error: 'Error saving chats' });
  }
});

// Chat: Get History
app.get('/api/get-chat/:userId', async (req, res) => {
  try {
    const chatData = await Chat.findOne({ userId: req.params.userId });
    res.json({ sessions: chatData ? chatData.sessions : [] });
  } catch (error) {
    res.status(500).json({ error: 'Error fetching chats' });
  }
});

// Profile: Update
app.post('/api/update-profile', async (req, res) => {
  try {
    // 1. Get data from frontend
    let { email, identifier, department, role, avatar, isNewAdmission, username } = req.body;

    // --- CRITICAL FIX FOR EMAIL ERROR ---
    // If email is an empty string, set it to NULL.
    // MongoDB allows multiple NULLs, but throws an error for multiple empty strings ("").
    if (email === "") {
      email = null;
    }

    // Update the user where 'username' matches
    const query = { username: username }; 

    const updatedUser = await User.findOneAndUpdate(
      query, 
      { 
        identifier, 
        department, 
        role, 
        avatar, 
        isNewAdmission,
        email, 
        updatedAt: new Date() 
      },
      { new: true } // Return the updated document
    );

    if (!updatedUser) {
        return res.status(404).json({ message: "User not found" });
    }

    res.status(200).json({ message: "Success", user: updatedUser });
  } catch (error) {
    console.error("Profile Update Error:", error);
    
    // Send a clearer error message back to the frontend
    if (error.code === 11000) {
        return res.status(400).json({ message: "This email is already in use by another student." });
    }
    
    res.status(500).json({ message: "Server Error" });
  }
});

const PORT = process.env.PORT || 5000;
app.listen(PORT, () => console.log(`🚀 Node Server running on port ${PORT}`));