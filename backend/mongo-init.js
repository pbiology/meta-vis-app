db = db.getSiblingDB('meta-vis-dev');
db.createUser({
  user: 'meta_vis_app',
  pwd: process.env.MONGO_APP_PASSWORD,
  roles: [{ role: 'readWrite', db: 'meta-vis-dev' }]
});