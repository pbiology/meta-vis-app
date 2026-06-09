FROM node:22-trixie-slim

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

# OpenShift/Kubernetes-compatible permissions:

# OpenShift may run the container with a random non-root UID,

# so make /app writable by the root group.

RUN chgrp -R 0 /app && chmod -R g=u /app

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]