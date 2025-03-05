const app = Vue.createApp({
    data() {
        return {
            gameState: { rooms: [] },
            selectedRoom: null,
            currentView: 'room',
            lastUpdated: '加载中...',
            autoRefresh: true,
            refreshInterval: 5,
            refreshTimer: null,
            apiBaseUrl: '/api',
            expandedTurns: [] // 存储已展开的回合ID
        };
    },
    computed: {
        currentMatch() {
            if (!this.selectedRoom || !this.selectedRoom.current_match_id) return null;
            return this.selectedRoom.matches.find(m => m.id === this.selectedRoom.current_match_id);
        },
        currentTurn() {
            if (!this.currentMatch || !this.currentMatch.current_turn_id) return null;
            return this.currentMatch.turns.find(t => t.id === this.currentMatch.current_turn_id);
        }
    },
    watch: {
        autoRefresh(newVal) {
            if (newVal) {
                this.startAutoRefresh();
            } else {
                this.stopAutoRefresh();
            }
        },
        refreshInterval() {
            if (this.autoRefresh) {
                this.restartAutoRefresh();
            }
        }
    },
    methods: {
        async refreshData() {
            try {
                const response = await axios.get(`${this.apiBaseUrl}/state`);
                this.gameState = response.data;
                this.lastUpdated = new Date().toLocaleTimeString();
                
                // 如果有选定的房间，更新选定的房间数据
                if (this.selectedRoom) {
                    const roomId = this.selectedRoom.id;
                    const updatedRoom = this.gameState.rooms.find(r => r.id === roomId);
                    if (updatedRoom) {
                        this.selectedRoom = updatedRoom;
                    }
                }
            } catch (error) {
                console.error('刷新数据出错:', error);
                this.lastUpdated = `更新失败: ${error.message}`;
            }
        },
        
        selectRoom(room) {
            this.selectedRoom = room;
            this.currentView = 'room';
        },
        
        getPlayerName(playerId) {
            if (!this.selectedRoom) return playerId;
            const player = this.selectedRoom.players.find(p => p.id === playerId);
            return player ? player.name : playerId;
        },
        
        formatDate(dateStr) {
            if (!dateStr) return '';
            const date = new Date(dateStr);
            return date.toLocaleString();
        },
        
        formatTime(dateStr) {
            if (!dateStr) return '';
            const date = new Date(dateStr);
            return date.toLocaleTimeString();
        },
        
        toggleTurnExpand(turnId) {
            // 切换回合的展开/折叠状态
            const index = this.expandedTurns.indexOf(turnId);
            if (index === -1) {
                this.expandedTurns.push(turnId);
            } else {
                this.expandedTurns.splice(index, 1);
            }
        },
        
        startAutoRefresh() {
            this.refreshTimer = setInterval(this.refreshData, this.refreshInterval * 1000);
        },
        
        stopAutoRefresh() {
            if (this.refreshTimer) {
                clearInterval(this.refreshTimer);
                this.refreshTimer = null;
            }
        },
        
        restartAutoRefresh() {
            this.stopAutoRefresh();
            this.startAutoRefresh();
        }
    },
    
    mounted() {
        // 初始化时获取数据
        this.refreshData();
        // 启动自动刷新
        if (this.autoRefresh) {
            this.startAutoRefresh();
        }
    },
    
    unmounted() {
        // 组件销毁时清除定时器
        this.stopAutoRefresh();
    }
});

app.mount('#app');
