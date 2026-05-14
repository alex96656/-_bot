const io = require("socket.io-client");
const socket = io("http://localhost:3000");

socket.on("broadcast", (msg) => {
  console.log("📢 Admin Broadcast:", msg);

  // Example: send to WhatsApp users
  // bot.sendMessage(jid, { text: msg });
});