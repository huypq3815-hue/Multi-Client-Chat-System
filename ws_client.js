// ================================================
// ChatSphere WebSocket Client – Professional Edition
// ================================================

class ChatClient {
  constructor() {
    this.ws = null;
    this.username = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 3000;

    this.$ = (id) => document.getElementById(id);
    this.loginScreen = this.$('login-screen');
    this.chatScreen = this.$('chat-screen');
    this.btnConnect = this.$('btnConnect');
    this.inputUser = this.$('username');
    this.userListEl = this.$('userList');
    this.messagesEl = this.$('messages');
    this.msgInput = this.$('msgInput');
    this.sendBtn = this.$('sendBtn');
    this.statusEl = this.$('connectionStatus');
    this.userCount = this.$('userCount');
    this.typingIndicator = this.$('typingIndicator');
    this.themeToggle = this.$('themeToggle');

    this.typingUsers = new Set();
    this.typingTimer = null;

    this.init();
  }

  init() {
    this.bindEvents();
    this.loadTheme();
  }

  bindEvents() {
    this.btnConnect.onclick = () => this.connect();
    this.inputUser.addEventListener('keydown', e => e.key === 'Enter' && this.connect());
    this.sendBtn.onclick = () => this.sendMessage();
    this.msgInput.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.sendMessage();
      }
    });
    this.msgInput.addEventListener('input', () => this.handleTyping());
    this.themeToggle.onclick = () => this.toggleTheme();
  }

  connect() {
    const name = this.inputUser.value.trim();
    if (!name || name.length > 24) {
      return this.showToast('Username must be 1–24 characters', 'error');
    }
    this.username = name;
    this.loginScreen.classList.remove('active');
    this.chatScreen.classList.add('active');
    this.connectWebSocket();
  }

  connectWebSocket() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}`;
    this.ws = new WebSocket("ws://localhost:6789");
;

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.setStatus('online', 'Connected');
      this.send({ type: 'login', username: this.username });
    };

    this.ws.onmessage = (evt) => this.handleMessage(JSON.parse(evt.data));
    this.ws.onclose = () => this.handleDisconnect();
    this.ws.onerror = () => this.appendSystem('Connection error');
  }

  handleMessage(msg) {
    switch (msg.type) {
      case 'user_list':
        this.renderUserList(msg.users);
        this.userCount.textContent = `${msg.users.length} online`;
        break;
      case 'system':
        this.appendSystem(msg.text);
        break;
      case 'group':
        this.appendMessage(msg.from, msg.text, false, msg.time);
        break;
      case 'private':
        const isMine = msg.from === this.username;
        this.appendMessage(msg.from, msg.text, isMine, msg.time, true);
        break;
      case 'typing':
        if (msg.isTyping) this.typingUsers.add(msg.from);
        else this.typingUsers.delete(msg.from);
        this.updateTypingIndicator();
        break;
      case 'user_joined':
        this.appendSystem(`${msg.username} joined`);
        break;
      case 'user_left':
        this.appendSystem(`${msg.username} left`);
        break;
    }
  }

  renderUserList(users) {
    this.userListEl.innerHTML = '';
    users.forEach(u => {
      const li = document.createElement('li');
      li.innerHTML = `<span class="status-dot"></span><span class="user-name">${this.escape(u)}</span>`;
      li.onclick = () => {
        this.msgInput.value = `@${u} `;
        this.msgInput.focus();
      };
      this.userListEl.appendChild(li);
    });
  }

  appendMessage(from, text, isMine, time, isPrivate = false) {
    const row = document.createElement('div');
    row.className = `msg-row ${isMine ? 'mine' : ''}`;
    const bubble = document.createElement('div');
    bubble.className = `message ${isMine ? 'mine' : 'theirs'} ${isPrivate ? 'private' : ''}`;
    bubble.innerHTML = `
      <div class="msg-header">
        <strong>${this.escape(from)}</strong>
        ${isPrivate ? `<span class="private-badge">Private</span>` : ''}
      </div>
      <div class="msg-body">${this.escape(text).replace(/\n/g, '<br>')}</div>
      <div class="msg-meta">${this.formatTime(time)}</div>
    `;
    row.appendChild(bubble);
    this.messagesEl.appendChild(row);
    this.scrollToBottom();
  }

  appendSystem(text) {
    const row = document.createElement('div');
    row.className = 'msg-row system';
    const msg = document.createElement('div');
    msg.className = 'message system';
    msg.textContent = text;
    row.appendChild(msg);
    this.messagesEl.appendChild(row);
    this.scrollToBottom();
  }

  sendMessage() {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return this.showToast('Not connected', 'error');
    }
    const text = this.msgInput.value.trim();
    if (!text) return;

    if (text.startsWith('@')) {
      const spaceIdx = text.indexOf(' ');
      if (spaceIdx === -1) return this.showToast('Use: @username message', 'error');
      const to = text.slice(1, spaceIdx);
      const body = text.slice(spaceIdx + 1);
      this.send({ type: 'private', to, text: body });
      this.appendMessage(this.username, body, true, new Date().toISOString(), true);
    } else {
      this.send({ type: 'group', text });
      this.appendMessage(this.username, text, true, new Date().toISOString());
    }
    this.msgInput.value = '';
    this.handleTyping(true);
  }

  handleTyping(stop = false) {
    clearTimeout(this.typingTimer);
    if (stop || !this.msgInput.value.trim()) {
      this.send({ type: 'typing', isTyping: false });
      return;
    }
    this.send({ type: 'typing', isTyping: true });
    this.typingTimer = setTimeout(() => {
      this.send({ type: 'typing', isTyping: false });
    }, 1000);
  }

  updateTypingIndicator() {
    if (this.typingUsers.size > 0) {
      const names = Array.from(this.typingUsers).slice(0, 3).join(', ');
      const more = this.typingUsers.size > 3 ? ` and ${this.typingUsers.size - 3} more` : '';
      this.typingIndicator.querySelector('.typing-text').textContent = `${names}${more} ${this.typingUsers.size > 1 ? 'are' : 'is'} typing...`;
      this.typingIndicator.classList.remove('hidden');
    } else {
      this.typingIndicator.classList.add('hidden');
    }
  }

  handleDisconnect() {
    this.setStatus('offline', 'Disconnected');
    this.appendSystem('Reconnecting...');
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      setTimeout(() => this.connectWebSocket(), this.reconnectDelay * this.reconnectAttempts);
    } else {
      this.showToast('Reconnect failed. Refresh page.', 'error');
    }
  }

  setStatus(type, text) {
    this.statusEl.className = `status ${type}`;
    this.statusEl.textContent = text;
  }

  scrollToBottom() {
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
  }

  formatTime(iso) {
    const date = new Date(iso);
    const now = new Date();
    const isToday = date.toDateString() === now.toDateString();
    return isToday
      ? date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      : date.toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  }

  escape(html) {
    const div = document.createElement('div');
    div.textContent = html;
    return div.innerHTML;
  }

  showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  toggleTheme() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const newTheme = isDark ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    this.themeToggle.textContent = newTheme === 'dark' ? 'Sun' : 'Moon';
  }

  loadTheme() {
    const saved = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const theme = saved || (prefersDark ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', theme);
    this.themeToggle.textContent = theme === 'dark' ? 'Sun' : 'Moon';
  }

  send(data) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ ...data, from: this.username }));
    }
  }
}

// Start
new ChatClient();