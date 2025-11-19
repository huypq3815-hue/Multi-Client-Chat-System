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
    this.emojiBtn = this.$('emojiBtn');
    this.emojiPicker = this.$('emojiPicker');
    this.sidebarToggle = this.$('sidebarToggle');
    this.sidebar = document.querySelector('.sidebar');

    this.typingUsers = new Set();
    this.typingTimer = null;
    this.userColors = {};

    this.emojis = [
      "😀","😃","😄","😁","😆","😅","😂","🤣","😊","😇","🙂","🙃","😉","😍","🥰","😘","😋","😛","😜","🤪","🤨","🤓","😎","🥳",
      "🥺","😢","😭","😤","😠","🤬","🤯","😳","🥵","🥶","😱","😨","😏","😒","😞","😔","😟","🙁","😣","😖","😫","😩",
      "🥱","😴","🤗","🤔","🤭","🤫","🤥","😶","😐","😑","😬","🙄","😯","😦","😧","😮","😲","🤐","🥴","🤧","😷","🤒","🤕",
      "😵","🤡","👻","💀","👽","🤖","💩","👍","👎","👊","✌️","🤞","🤟","🤘","👌","🤌","❤️","💔","💕","💖","💙","💜","🧡","💛","💚","⭐","🌟","✨","🔥","💯","🎉","🎊"
    ];

    this.init();
  }

  init() {
    this.bindEvents();
    this.loadTheme();
    this.populateEmojiPicker();
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
    this.emojiBtn.onclick = () => this.emojiPicker.classList.toggle('hidden');
    this.sidebarToggle.onclick = () => this.sidebar.classList.toggle('open');

    document.addEventListener('click', (e) => {
      if (!this.emojiPicker.classList.contains('hidden') &&
          !this.emojiBtn.contains(e.target) &&
          !this.emojiPicker.contains(e.target)) {
        this.emojiPicker.classList.add('hidden');
      }
    });
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
    // Kết nối trực tiếp tới server Python đang chạy ở port 6789
    this.ws = new WebSocket("ws://127.0.0.1:6789");

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.setStatus('online', 'Connected');
      this.send({ type: 'login', username: this.username });
    };

    this.ws.onmessage = (evt) => this.handleMessage(JSON.parse(evt.data));
    this.ws.onclose = () => this.handleDisconnect();
    this.ws.onerror = () => this.appendSystem('Connection error');

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
      const color = this.getUserColor(u);
      const initials = this.getInitials(u);
      const li = document.createElement('li');
      const avatar = document.createElement('div');
      avatar.className = 'avatar';
      avatar.style.backgroundColor = color;
      avatar.textContent = initials;
      const nameSpan = document.createElement('span');
      nameSpan.className = 'user-name';
      nameSpan.style.color = color;
      nameSpan.textContent = this.escape(u);
      li.appendChild(avatar);
      li.appendChild(nameSpan);
      li.onclick = () => {
        this.msgInput.value = `@${u} `;
        this.msgInput.focus();
      };
      this.userListEl.appendChild(li);
    });
  }

  appendMessage(from, text, isMine, time, isPrivate = false, privateTo = null) {
    const row = document.createElement('div');
    row.className = `msg-row ${isMine ? 'mine' : ''}`;
    const color = this.getUserColor(from);
    const initials = this.getInitials(from);
    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.style.backgroundColor = color;
    avatar.textContent = initials;

    const bubble = document.createElement('div');
    bubble.className = `message ${isMine ? 'mine' : 'theirs'} ${isPrivate ? 'private' : ''}`;

    let headerText = this.escape(from);
    let badge = isPrivate ? '<span class="private-badge">Private</span>' : '';
    if (isPrivate) {
      if (isMine && privateTo) {
        headerText = `You → ${this.escape(privateTo)}`;
      } else if (!isMine) {
        headerText = `${this.escape(from)} → You`;
      }
    }

    bubble.innerHTML = `
      <div class="msg-header">
        <strong style="color: ${color}">${headerText}</strong>
        ${badge}
      </div>
      <div class="msg-body">${this.escape(text).replace(/\n/g, '<br>')}</div>
      <div class="msg-meta">${this.formatTime(time)}</div>
    `;

    if (isMine) {
      row.appendChild(bubble);
      row.appendChild(avatar);
    } else {
      row.appendChild(avatar);
      row.appendChild(bubble);
    }

    this.messagesEl.appendChild(row);

    // Animation
    row.style.opacity = '0';
    row.style.transform = 'translateY(10px)';
    requestAnimationFrame(() => {
      row.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
      row.style.opacity = '1';
      row.style.transform = 'translateY(0)';
    });

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

    row.style.opacity = '0';
    row.style.transform = 'translateY(10px)';
    requestAnimationFrame(() => {
      row.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
      row.style.opacity = '1';
      row.style.transform = 'translateY(0)';
    });

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
      this.appendMessage(this.username, body, true, new Date().toISOString(), true, to);
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
    this.themeToggle.textContent = newTheme === 'dark' ? '☀️' : '🌙';
  }

  loadTheme() {
    const saved = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const theme = saved || (prefersDark ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', theme);
    this.themeToggle.textContent = theme === 'dark' ? '☀️' : '🌙';
  }

  populateEmojiPicker() {
    this.emojiPicker.innerHTML = this.emojis.map(emoji => `<span class="emoji">${emoji}</span>`).join('');
    this.emojiPicker.addEventListener('click', e => {
      if (e.target.classList.contains('emoji')) {
        this.insertAtCursor(e.target.textContent);
        this.emojiPicker.classList.add('hidden');
      }
    });
  }

  insertAtCursor(text) {
    const input = this.msgInput;
    const start = input.selectionStart || 0;
    const end = input.selectionEnd || 0;
    input.value = input.value.slice(0, start) + text + input.value.slice(end);
    input.selectionStart = input.selectionEnd = start + text.length;
    input.focus();
    this.handleTyping();
  }

  stringToColor(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    const h = Math.abs(hash % 360);
    return `hsl(${h}, 70%, 50%)`;
  }

  getUserColor(username) {
    if (!this.userColors[username]) {
      this.userColors[username] = this.stringToColor(username);
    }
    return this.userColors[username];
  }

  getInitials(username) {
    return username.slice(0, 2).toUpperCase();
  }

  send(data) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ ...data, from: this.username }));
    }
  }
}

// Start
new ChatClient();