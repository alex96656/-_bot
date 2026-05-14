const express = require("express");
const session = require("express-session");
const bodyParser = require("body-parser");
const http = require("http");
const { Server } = require("socket.io");

const app = express();
const server = http.createServer(app);
const io = new Server(server);

app.use(bodyParser.json());

app.use(session({
  secret: "super_secret_key",
  resave: false,
  saveUninitialized: true
}));

app.use(express.static("admin-panel"));

/* ======================
   LOGIN SYSTEM
====================== */

app.post("/login", (req, res) => {
  const { username, password } = req.body;

  if (username === "admin" && password === "admin123") {
    req.session.auth = true;
    return res.json({ success: true });
  }

  res.json({ success: false });
});

function auth(req, res, next) {
  if (req.session.auth) return next();
  res.redirect("/");
}

/* ======================
   DASHBOARD PAGE
====================== */

app.get("/dashboard", auth, (req, res) => {
  res.sendFile(__dirname + "/admin-panel/dashboard.html");
});

/* ======================
   BOT CONTROL BRIDGE
====================== */

let botStatus = "online";

app.get("/status", auth, (req, res) => {
  res.json({ status: botStatus });
});

/* Broadcast to bot */
app.post("/broadcast", auth, (req, res) => {
  const { message } = req.body;

  io.emit("broadcast", message);

  res.json({ success: true });
});

/* Socket connection */
io.on("connection", (socket) => {
  console.log("Admin connected");
});

server.listen(3000, () => {
  console.log("🔥 Admin Panel running: http://localhost:3000");
});