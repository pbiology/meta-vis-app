db = db.getSiblingDB('admin');
db.createUser({
  user: process.env.MONGODB_USERNAME,
  pwd: process.env.MONGO_APP_PASSWORD,
  roles: [{ role: 'readWrite', db: process.env.MONGODB_DB_NAME }]
});