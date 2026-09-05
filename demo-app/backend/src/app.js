const express = require('express');
const projectsRouter = require('./routes/projects');

function createApp() {
  const app = express();
  app.use(express.json());
  app.use('/api/projects', projectsRouter);
  return app;
}

module.exports = createApp;
