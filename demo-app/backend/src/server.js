const createApp = require('./app');

const PORT = process.env.PORT || 4000;
const app = createApp();

app.listen(PORT, () => {
  console.log(`API server listening on http://localhost:${PORT}`);
});
