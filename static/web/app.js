// API基础URL
const API_BASE_URL = '/api';

// 创建Vue应用
const app = Vue.createApp({
    data() {
        return {
            // 认证相关
            isAuthenticated: false,
            authMode: 'login',
            loginForm: {
                username: '',
                password: ''
            },
            registerForm: {
                username: '',
                email: '',
                password: ''
            },
            loginError: null,
            registerError: null,
            
            // 用户信息
            user: {
                id: '',
                username: '',
                email: ''
            },
            token: '',
            
            // 视图控制
            currentView: 'rooms',
            
            // 房间相关
            rooms: [],
            selectedRoom: null,
            showCreateRoomModal: false,
            createRoomForm: {
                name: ''
            },
            
            // 当前房间
            currentRoom: null,
            
            // 游戏相关
            gameMessages: [],
            actionInput: '',
            showStartGameModal: false,
            startGameForm: {
                scenario_id: '',
                scene: '默认场景'
            },
            scenarios: [],
            
            // WebSocket连接
            socket: null,
            
            // 通知
            notification: {
                show: false,
                message: '',
                type: 'info',
                timeout: null
            }
        };
    },
    
    computed: {
        // 判断当前用户是否是房主
        isCurrentUserHost() {
            if (!this.currentRoom || !this.user.id) return false;
            return this.currentRoom.host_id === this.user.id;
        },
        
        // 判断当前用户是否已准备
        isCurrentUserReady() {
            if (!this.currentRoom || !this.user.id) return false;
            
            const currentPlayer = this.currentRoom.players.find(player => player.id === this.user.id);
            return currentPlayer ? currentPlayer.is_ready : false;
        }
    },
    
    created() {
        // 检查本地存储中的认证信息
        const token = localStorage.getItem('token');
        const user = localStorage.getItem('user');
        
        if (token && user) {
            this.token = token;
            this.user = JSON.parse(user);
            this.isAuthenticated = true;
            
            // 设置axios默认头部
            axios.defaults.headers.common['Authorization'] = `Bearer ${this.token}`;
            
            // 加载初始数据
            this.loadRooms();
            this.loadScenarios();
            
            // 连接WebSocket
            this.connectWebSocket();
        }
    },
    
    methods: {
        // 认证相关方法
        async login() {
            try {
                this.loginError = null;
                
                // 创建表单数据
                const formData = new FormData();
                formData.append('username', this.loginForm.username);
                formData.append('password', this.loginForm.password);
                
                // 发送登录请求
                const response = await axios.post(`${API_BASE_URL}/users/token`, formData);
                
                // 保存认证信息
                this.token = response.data.access_token;
                this.user = {
                    id: response.data.user_id,
                    username: response.data.username
                };
                
                // 存储到本地
                localStorage.setItem('token', this.token);
                localStorage.setItem('user', JSON.stringify(this.user));
                
                // 设置axios默认头部
                axios.defaults.headers.common['Authorization'] = `Bearer ${this.token}`;
                
                // 更新认证状态
                this.isAuthenticated = true;
                
                // 加载初始数据
                this.loadRooms();
                this.loadScenarios();
                
                // 连接WebSocket
                this.connectWebSocket();
                
                // 显示通知
                this.showNotification('登录成功', 'success');
            } catch (error) {
                console.error('登录失败:', error);
                this.loginError = error.response?.data?.detail || '登录失败，请检查用户名和密码';
            }
        },
        
        async register() {
            try {
                this.registerError = null;
                
                // 发送注册请求
                const response = await axios.post(`${API_BASE_URL}/users/register`, {
                    username: this.registerForm.username,
                    email: this.registerForm.email,
                    password: this.registerForm.password
                });
                
                // 保存认证信息
                this.token = response.data.access_token;
                this.user = {
                    id: response.data.user_id,
                    username: response.data.username
                };
                
                // 存储到本地
                localStorage.setItem('token', this.token);
                localStorage.setItem('user', JSON.stringify(this.user));
                
                // 设置axios默认头部
                axios.defaults.headers.common['Authorization'] = `Bearer ${this.token}`;
                
                // 更新认证状态
                this.isAuthenticated = true;
                
                // 加载初始数据
                this.loadRooms();
                this.loadScenarios();
                
                // 连接WebSocket
                this.connectWebSocket();
                
                // 显示通知
                this.showNotification('注册成功', 'success');
            } catch (error) {
                console.error('注册失败:', error);
                this.registerError = error.response?.data?.detail || '注册失败，请检查输入信息';
            }
        },
        
        logout() {
            // 断开WebSocket连接
            if (this.socket) {
                this.socket.close();
                this.socket = null;
            }
            
            // 清除认证信息
            this.token = '';
            this.user = {
                id: '',
                username: '',
                email: ''
            };
            this.isAuthenticated = false;
            
            // 清除本地存储
            localStorage.removeItem('token');
            localStorage.removeItem('user');
            
            // 清除axios默认头部
            delete axios.defaults.headers.common['Authorization'];
            
            // 重置表单
            this.loginForm = {
                username: '',
                password: ''
            };
            this.registerForm = {
                username: '',
                email: '',
                password: ''
            };
            
            // 显示通知
            this.showNotification('已退出登录', 'info');
        },
        
        // 房间相关方法
        async loadRooms() {
            try {
                const response = await axios.get(`${API_BASE_URL}/rooms/`);
                this.rooms = response.data;
            } catch (error) {
                console.error('加载房间列表失败:', error);
                this.showNotification('加载房间列表失败', 'error');
            }
        },
        
        selectRoom(room) {
            this.selectedRoom = room;
        },
        
        async createRoom() {
            try {
                const response = await axios.post(`${API_BASE_URL}/rooms/`, {
                    name: this.createRoomForm.name || `${this.user.username}的房间`
                });
                
                // 添加到房间列表
                this.rooms.push(response.data);
                
                // 关闭模态框
                this.showCreateRoomModal = false;
                
                // 重置表单
                this.createRoomForm.name = '';
                
                // 显示通知
                this.showNotification('房间创建成功', 'success');
                
                // 加入房间
                await this.joinRoom(response.data);
            } catch (error) {
                console.error('创建房间失败:', error);
                this.showNotification('创建房间失败', 'error');
            }
        },
        
        async joinRoom(room) {
            try {
                const response = await axios.post(`${API_BASE_URL}/rooms/${room.id}/join`);
                
                // 获取房间详情
                await this.loadRoomDetail(room.id);
                
                // 切换到游戏视图
                this.currentView = 'game';
                
                // 关闭房间详情模态框
                this.selectedRoom = null;
                
                // 显示通知
                this.showNotification(`已加入房间: ${room.name}`, 'success');
                
                // 添加系统消息
                this.addSystemMessage(`你已加入房间: ${room.name}`);
            } catch (error) {
                console.error('加入房间失败:', error);
                this.showNotification('加入房间失败', 'error');
            }
        },
        
        async loadRoomDetail(roomId) {
            try {
                const response = await axios.get(`${API_BASE_URL}/rooms/${roomId}`);
                this.currentRoom = response.data;
            } catch (error) {
                console.error('加载房间详情失败:', error);
                this.showNotification('加载房间详情失败', 'error');
            }
        },
        
        async leaveRoom() {
            if (!this.currentRoom) return;
            
            try {
                const response = await axios.post(`${API_BASE_URL}/rooms/${this.currentRoom.id}/leave`);
                
                // 重置当前房间
                this.currentRoom = null;
                
                // 清空游戏消息
                this.gameMessages = [];
                
                // 切换到房间列表视图
                this.currentView = 'rooms';
                
                // 重新加载房间列表
                await this.loadRooms();
                
                // 显示通知
                this.showNotification('已离开房间', 'info');
            } catch (error) {
                console.error('离开房间失败:', error);
                this.showNotification('离开房间失败', 'error');
            }
        },
        
        // 游戏相关方法
        async loadScenarios() {
            try {
                const response = await axios.get(`${API_BASE_URL}/game/scenarios`);
                this.scenarios = response.data;
            } catch (error) {
                console.error('加载剧本列表失败:', error);
                this.showNotification('加载剧本列表失败', 'error');
            }
        },
        
        async startGame() {
            if (!this.currentRoom) return;
            
            // 检查是否是房主
            if (!this.isCurrentUserHost) {
                this.showNotification('只有房主可以开始游戏', 'error');
                return;
            }
            
            // 检查是否所有玩家都已准备
            if (!this.currentRoom.all_players_ready && this.currentRoom.players.length > 1) {
                this.showNotification('还有玩家未准备，无法开始游戏', 'error');
                return;
            }
            
            try {
                const response = await axios.post(`${API_BASE_URL}/rooms/${this.currentRoom.id}/start`, {
                    scene: this.startGameForm.scene,
                    scenario_id: this.startGameForm.scenario_id || null
                });
                
                // 更新当前房间
                await this.loadRoomDetail(this.currentRoom.id);
                
                // 关闭模态框
                this.showStartGameModal = false;
                
                // 重置表单
                this.startGameForm = {
                    scenario_id: '',
                    scene: '默认场景'
                };
                
                // 显示通知
                this.showNotification('游戏已开始', 'success');
                
                // 添加系统消息
                this.addSystemMessage('游戏已开始');
            } catch (error) {
                console.error('开始游戏失败:', error);
                this.showNotification('开始游戏失败: ' + (error.response?.data?.detail || '未知错误'), 'error');
            }
        },
        
        // 设置玩家准备状态
        async setReady(isReady) {
            if (!this.currentRoom) return;
            
            try {
                const response = await axios.post(`${API_BASE_URL}/rooms/${this.currentRoom.id}/ready`, {
                    is_ready: isReady
                });
                
                // 更新当前房间
                await this.loadRoomDetail(this.currentRoom.id);
                
                // 显示通知
                this.showNotification(isReady ? '已准备' : '已取消准备', 'success');
                
                // 添加系统消息
                this.addSystemMessage(isReady ? '你已准备' : '你已取消准备');
            } catch (error) {
                console.error('设置准备状态失败:', error);
                this.showNotification('设置准备状态失败: ' + (error.response?.data?.detail || '未知错误'), 'error');
            }
        },
        
        // 踢出玩家
        async kickPlayer(playerId) {
            if (!this.currentRoom) return;
            
            // 检查是否是房主
            if (!this.isCurrentUserHost) {
                this.showNotification('只有房主可以踢出玩家', 'error');
                return;
            }
            
            try {
                const response = await axios.post(`${API_BASE_URL}/rooms/${this.currentRoom.id}/kick/${playerId}`);
                
                // 更新当前房间
                await this.loadRoomDetail(this.currentRoom.id);
                
                // 显示通知
                this.showNotification('玩家已被踢出', 'success');
                
                // 添加系统消息
                this.addSystemMessage('你踢出了一名玩家');
            } catch (error) {
                console.error('踢出玩家失败:', error);
                this.showNotification('踢出玩家失败: ' + (error.response?.data?.detail || '未知错误'), 'error');
            }
        },
        
        async sendAction() {
            if (!this.actionInput.trim()) return;
            
            try {
                // 发送行动
                await axios.post(`${API_BASE_URL}/game/action`, {
                    action: this.actionInput
                });
                
                // 添加玩家消息
                this.addPlayerMessage(this.user.username, this.actionInput);
                
                // 清空输入
                this.actionInput = '';
            } catch (error) {
                console.error('发送行动失败:', error);
                this.showNotification('发送行动失败', 'error');
            }
        },
        
        // WebSocket相关方法
        connectWebSocket() {
            // 如果已经连接，先断开
            if (this.socket) {
                this.socket.close();
            }
            
            // 创建WebSocket连接
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/api/game/ws`;
            
            this.socket = new WebSocket(wsUrl);
            
            // 连接建立时
            this.socket.onopen = () => {
                console.log('WebSocket连接已建立');
                
                // 发送认证消息
                this.socket.send(JSON.stringify({
                    token: this.token
                }));
                
                // 显示通知
                this.showNotification('已连接到游戏服务器', 'success');
            };
            
            // 接收消息时
            this.socket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    
                    if (data.type === 'message') {
                        // 解析消息内容
                        const content = data.content;
                        
                        // 判断消息类型
                        if (content.startsWith('DM:')) {
                            // DM消息
                            this.addDMMessage(content.substring(3).trim());
                        } else if (content.includes(':')) {
                            // 玩家消息
                            const parts = content.split(':', 2);
                            this.addPlayerMessage(parts[0].trim(), parts[1].trim());
                        } else {
                            // 系统消息
                            this.addSystemMessage(content);
                        }
                    }
                } catch (error) {
                    console.error('解析WebSocket消息失败:', error);
                }
            };
            
            // 连接关闭时
            this.socket.onclose = () => {
                console.log('WebSocket连接已关闭');
                
                // 如果是认证状态，尝试重新连接
                if (this.isAuthenticated) {
                    setTimeout(() => {
                        this.connectWebSocket();
                    }, 3000);
                }
            };
            
            // 连接错误时
            this.socket.onerror = (error) => {
                console.error('WebSocket连接错误:', error);
                this.showNotification('游戏服务器连接错误', 'error');
            };
        },
        
        // 消息相关方法
        addSystemMessage(content) {
            this.gameMessages.push({
                type: 'system',
                content: content
            });
            this.scrollToBottom();
        },
        
        addDMMessage(content) {
            this.gameMessages.push({
                type: 'dm',
                content: content
            });
            this.scrollToBottom();
        },
        
        addPlayerMessage(sender, content) {
            this.gameMessages.push({
                type: 'player',
                sender: sender,
                content: content
            });
            this.scrollToBottom();
        },
        
        scrollToBottom() {
            // 滚动到底部
            this.$nextTick(() => {
                const messagesContainer = document.querySelector('.game-messages');
                if (messagesContainer) {
                    messagesContainer.scrollTop = messagesContainer.scrollHeight;
                }
            });
        },
        
        // 通知相关方法
        showNotification(message, type = 'info') {
            // 清除之前的定时器
            if (this.notification.timeout) {
                clearTimeout(this.notification.timeout);
            }
            
            // 设置通知
            this.notification.show = true;
            this.notification.message = message;
            this.notification.type = type;
            
            // 3秒后自动关闭
            this.notification.timeout = setTimeout(() => {
                this.notification.show = false;
            }, 3000);
        }
    }
});

// 挂载Vue应用
app.mount('#app');
