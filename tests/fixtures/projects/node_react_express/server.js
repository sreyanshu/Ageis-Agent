const express = require('express');
const app = express();
app.use(express.json());

app.get('/api/health', (req, res) => {
  res.json({ status: 'ok' });
});

app.post('/api/users', (req, res) => {
  res.status(201).json({ id: 1, name: req.body.name });
});

module.exports = app;
