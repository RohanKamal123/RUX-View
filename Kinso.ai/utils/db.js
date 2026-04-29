const fs = require('fs');
const path = require('path');

const DB_PATH = path.join(__dirname, '..', 'users.json');

function loadUsers() {
    if (!fs.existsSync(DB_PATH)) {
        return [];
    }
    try {
        const data = fs.readFileSync(DB_PATH, 'utf8');
        return JSON.parse(data);
    } catch (err) {
        console.error('Error reading users.json:', err);
        return [];
    }
}

function saveUser(user) {
    const users = loadUsers();
    const existingIndex = users.findIndex(u => u.email === user.email);

    if (existingIndex >= 0) {
        users[existingIndex] = { ...users[existingIndex], ...user };
    } else {
        users.push(user);
    }

    try {
        fs.writeFileSync(DB_PATH, JSON.stringify(users, null, 2));
        console.log(`User ${user.email} saved successfully.`);
    } catch (err) {
        console.error('Error writing to users.json:', err);
    }
}

function getUser(email) {
    const users = loadUsers();
    return users.find(u => u.email === email);
}

module.exports = { saveUser, getUser };
