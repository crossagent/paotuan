/**
 * 剧本编辑器
 * 用于编辑和管理游戏剧本的JSON结构
 */

// 全局变量
let scriptData = null; // 当前加载的剧本数据
let currentMode = 'tree'; // 当前编辑模式：tree 或 json
let currentNodePath = []; // 当前选中节点的路径
let requiredNodes = [ // 必需的顶级节点
    '胜利条件',
    '失败条件',
    '世界背景与主要场景',
    '地图与谜题设置',
    '重要角色',
    '事件脉络'
];

// DOM元素引用
const elements = {
    loadBtn: document.getElementById('loadBtn'),
    saveBtn: document.getElementById('saveBtn'),
    viewModeBtn: document.getElementById('viewModeBtn'),
    modeSwitchBtns: document.querySelectorAll('.mode-switch'),
    scriptTree: document.getElementById('scriptTree'),
    treeEditMode: document.getElementById('treeEditMode'),
    jsonEditMode: document.getElementById('jsonEditMode'),
    jsonEditor: document.getElementById('jsonEditor'),
    formatJsonBtn: document.getElementById('formatJsonBtn'),
    validateJsonBtn: document.getElementById('validateJsonBtn'),
    currentNodePath: document.getElementById('currentNodePath'),
    nodeEditor: document.getElementById('nodeEditor'),
    addItemBtn: document.getElementById('addItemBtn'),
    deleteItemBtn: document.getElementById('deleteItemBtn'),
    alertModal: new bootstrap.Modal(document.getElementById('alertModal')),
    alertModalTitle: document.getElementById('alertModalTitle'),
    alertModalBody: document.getElementById('alertModalBody'),
    addItemModal: new bootstrap.Modal(document.getElementById('addItemModal')),
    newItemKey: document.getElementById('newItemKey'),
    newItemType: document.getElementById('newItemType'),
    newItemValue: document.getElementById('newItemValue'),
    newItemValueContainer: document.getElementById('newItemValueContainer'),
    confirmAddItem: document.getElementById('confirmAddItem')
};

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    // 绑定事件处理程序
    bindEventHandlers();
    
    // 尝试加载示例数据
    loadExampleData();
});

/**
 * 绑定事件处理程序
 */
function bindEventHandlers() {
    // 文件操作按钮
    elements.loadBtn.addEventListener('click', handleLoadFile);
    elements.saveBtn.addEventListener('click', handleSaveFile);
    
    // 编辑模式切换
    elements.modeSwitchBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            switchEditMode(e.target.dataset.mode);
        });
    });
    
    // JSON编辑器按钮
    elements.formatJsonBtn.addEventListener('click', formatJsonEditor);
    elements.validateJsonBtn.addEventListener('click', validateAndApplyJson);
    
    // 节点操作按钮
    elements.addItemBtn.addEventListener('click', showAddItemModal);
    elements.deleteItemBtn.addEventListener('click', handleDeleteItem);
    
    // 添加项目模态框
    elements.newItemType.addEventListener('change', toggleNewItemValueInput);
    elements.confirmAddItem.addEventListener('click', handleAddItem);
}

/**
 * 加载示例数据
 */
function loadExampleData() {
    // 这里可以加载一个默认的示例数据结构
    // 实际应用中可能会从localStorage或其他地方加载上次编辑的数据
    try {
        // 尝试从localStorage加载上次编辑的数据
        const savedData = localStorage.getItem('scriptEditorData');
        if (savedData) {
            scriptData = JSON.parse(savedData);
            refreshUI();
            showAlert('信息', '已加载上次编辑的数据');
        }
    } catch (error) {
        console.error('加载保存的数据失败:', error);
    }
}

/**
 * 处理加载文件
 */
function handleLoadFile() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    
    input.onchange = (e) => {
        const file = e.target.files[0];
        if (!file) return;
        
        const reader = new FileReader();
        reader.onload = (event) => {
            try {
                const data = JSON.parse(event.target.result);
                
                // 验证数据结构
                if (validateScriptStructure(data)) {
                    scriptData = data;
                    refreshUI();
                    showAlert('成功', '剧本加载成功！');
                    
                    // 保存到localStorage
                    localStorage.setItem('scriptEditorData', JSON.stringify(scriptData));
                }
            } catch (error) {
                showAlert('错误', `JSON解析失败: ${error.message}`);
            }
        };
        
        reader.readAsText(file);
    };
    
    input.click();
}

/**
 * 处理保存文件
 */
function handleSaveFile() {
    if (!scriptData) {
        showAlert('错误', '没有可保存的数据');
        return;
    }
    
    // 如果当前在JSON编辑模式，先应用更改
    if (currentMode === 'json') {
        if (!validateAndApplyJson()) {
            return;
        }
    }
    
    // 验证数据结构
    if (!validateScriptStructure(scriptData)) {
        return;
    }
    
    // 创建下载链接
    const dataStr = JSON.stringify(scriptData, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = 'scenario.json';
    document.body.appendChild(a);
    a.click();
    
    // 清理
    setTimeout(() => {
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }, 0);
    
    showAlert('成功', '剧本保存成功！');
}

/**
 * 切换编辑模式
 * @param {string} mode - 'tree' 或 'json'
 */
function switchEditMode(mode) {
    if (mode === currentMode) return;
    
    // 如果从JSON模式切换到树形模式，需要先验证并应用JSON
    if (currentMode === 'json' && mode === 'tree') {
        if (!validateAndApplyJson()) {
            return;
        }
    }
    
    // 如果从树形模式切换到JSON模式，需要更新JSON编辑器内容
    if (currentMode === 'tree' && mode === 'json') {
        elements.jsonEditor.value = JSON.stringify(scriptData, null, 2);
    }
    
    // 更新UI
    if (mode === 'tree') {
        elements.treeEditMode.style.display = 'block';
        elements.jsonEditMode.style.display = 'none';
    } else {
        elements.treeEditMode.style.display = 'none';
        elements.jsonEditMode.style.display = 'block';
    }
    
    currentMode = mode;
    elements.viewModeBtn.textContent = mode === 'tree' ? '树形编辑模式' : 'JSON编辑模式';
}

/**
 * 格式化JSON编辑器内容
 */
function formatJsonEditor() {
    try {
        const json = JSON.parse(elements.jsonEditor.value);
        elements.jsonEditor.value = JSON.stringify(json, null, 2);
    } catch (error) {
        showAlert('错误', `JSON格式化失败: ${error.message}`);
    }
}

/**
 * 验证并应用JSON编辑器内容
 * @returns {boolean} 验证是否成功
 */
function validateAndApplyJson() {
    try {
        const json = JSON.parse(elements.jsonEditor.value);
        
        // 验证数据结构
        if (validateScriptStructure(json)) {
            scriptData = json;
            
            // 保存到localStorage
            localStorage.setItem('scriptEditorData', JSON.stringify(scriptData));
            
            // 刷新树形结构
            renderScriptTree();
            
            showAlert('成功', 'JSON已验证并应用');
            return true;
        }
        
        return false;
    } catch (error) {
        showAlert('错误', `JSON验证失败: ${error.message}`);
        return false;
    }
}

/**
 * 验证剧本结构
 * @param {Object} data - 要验证的数据
 * @returns {boolean} 验证是否成功
 */
function validateScriptStructure(data) {
    // 检查必需的顶级节点
    const missingNodes = [];
    
    for (const node of requiredNodes) {
        if (!data.hasOwnProperty(node)) {
            missingNodes.push(node);
        }
    }
    
    if (missingNodes.length > 0) {
        showAlert('错误', `缺少必需的节点: ${missingNodes.join(', ')}`);
        return false;
    }
    
    // 可以添加更多的验证逻辑，例如检查特定节点的类型等
    
    return true;
}

/**
 * 刷新UI
 */
function refreshUI() {
    if (scriptData) {
        renderScriptTree();
        
        if (currentMode === 'json') {
            elements.jsonEditor.value = JSON.stringify(scriptData, null, 2);
        }
    }
}

/**
 * 渲染剧本树形结构
 */
function renderScriptTree() {
    elements.scriptTree.innerHTML = '';
    
    if (!scriptData) return;
    
    // 为每个顶级节点创建树节点
    for (const key in scriptData) {
        const node = createTreeNode(key, scriptData[key], [key]);
        elements.scriptTree.appendChild(node);
    }
}

/**
 * 创建树节点
 * @param {string} key - 节点键名
 * @param {*} value - 节点值
 * @param {Array} path - 节点路径
 * @returns {HTMLElement} 树节点元素
 */
function createTreeNode(key, value, path) {
    const nodeType = getValueType(value);
    const isExpandable = nodeType === 'object' || nodeType === 'array';
    
    // 创建节点容器
    const nodeContainer = document.createElement('div');
    nodeContainer.className = 'tree-node';
    nodeContainer.dataset.path = path.join('.');
    
    // 创建节点内容
    const nodeContent = document.createElement('div');
    nodeContent.className = 'node-content';
    
    // 创建展开/折叠图标
    if (isExpandable) {
        const toggleIcon = document.createElement('span');
        toggleIcon.className = 'node-toggle bi bi-caret-right';
        toggleIcon.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleNodeExpansion(nodeContainer);
        });
        nodeContent.appendChild(toggleIcon);
    } else {
        // 为非可展开节点添加占位符
        const spacer = document.createElement('span');
        spacer.style.width = '15px';
        spacer.style.display = 'inline-block';
        nodeContent.appendChild(spacer);
    }
    
    // 创建节点标签
    const nodeLabel = document.createElement('span');
    nodeLabel.className = 'node-label';
    nodeLabel.textContent = key;
    nodeContent.appendChild(nodeLabel);
    
    // 创建节点类型标签
    const nodeTypeSpan = document.createElement('span');
    nodeTypeSpan.className = `node-type ${nodeType}`;
    nodeTypeSpan.textContent = getTypeDisplayName(nodeType);
    nodeContent.appendChild(nodeTypeSpan);
    
    nodeContainer.appendChild(nodeContent);
    
    // 为可展开节点创建子节点容器
    if (isExpandable) {
        const childrenContainer = document.createElement('div');
        childrenContainer.className = 'node-children';
        
        // 根据值类型创建子节点
        if (nodeType === 'array') {
            value.forEach((item, index) => {
                const childPath = [...path, index];
                const childNode = createTreeNode(`[${index}]`, item, childPath);
                childrenContainer.appendChild(childNode);
            });
        } else if (nodeType === 'object') {
            for (const childKey in value) {
                const childPath = [...path, childKey];
                const childNode = createTreeNode(childKey, value[childKey], childPath);
                childrenContainer.appendChild(childNode);
            }
        }
        
        nodeContainer.appendChild(childrenContainer);
    }
    
    // 添加点击事件
    nodeContainer.addEventListener('click', (e) => {
        e.stopPropagation();
        selectNode(path);
    });
    
    return nodeContainer;
}

/**
 * 切换节点展开/折叠状态
 * @param {HTMLElement} nodeElement - 节点元素
 */
function toggleNodeExpansion(nodeElement) {
    const toggleIcon = nodeElement.querySelector('.node-toggle');
    const childrenContainer = nodeElement.querySelector('.node-children');
    
    if (toggleIcon && childrenContainer) {
        toggleIcon.classList.toggle('expanded');
        childrenContainer.classList.toggle('expanded');
        
        if (toggleIcon.classList.contains('expanded')) {
            toggleIcon.classList.replace('bi-caret-right', 'bi-caret-down');
        } else {
            toggleIcon.classList.replace('bi-caret-down', 'bi-caret-right');
        }
    }
}

/**
 * 选择节点
 * @param {Array} path - 节点路径
 */
function selectNode(path) {
    // 更新当前节点路径
    currentNodePath = path;
    
    // 更新节点选中状态
    const allNodes = document.querySelectorAll('.tree-node');
    allNodes.forEach(node => node.classList.remove('active'));
    
    const selectedNode = document.querySelector(`.tree-node[data-path="${path.join('.')}"]`);
    if (selectedNode) {
        selectedNode.classList.add('active');
        
        // 确保节点可见（展开父节点）
        let parent = selectedNode.parentElement;
        while (parent && parent.classList.contains('node-children')) {
            parent.classList.add('expanded');
            const parentNode = parent.parentElement;
            const toggleIcon = parentNode.querySelector('.node-toggle');
            if (toggleIcon) {
                toggleIcon.classList.add('expanded');
                toggleIcon.classList.replace('bi-caret-right', 'bi-caret-down');
            }
            parent = parentNode.parentElement;
        }
    }
    
    // 更新路径导航
    updatePathNavigation();
    
    // 渲染节点编辑器
    renderNodeEditor();
}

/**
 * 更新路径导航
 */
function updatePathNavigation() {
    elements.currentNodePath.innerHTML = '';
    
    currentNodePath.forEach((segment, index) => {
        // 创建路径段
        const segmentSpan = document.createElement('span');
        segmentSpan.className = 'path-segment';
        segmentSpan.textContent = segment;
        segmentSpan.dataset.index = index;
        segmentSpan.addEventListener('click', () => {
            selectNode(currentNodePath.slice(0, index + 1));
        });
        
        elements.currentNodePath.appendChild(segmentSpan);
        
        // 添加分隔符（除了最后一个）
        if (index < currentNodePath.length - 1) {
            const separator = document.createElement('span');
            separator.className = 'path-separator';
            separator.textContent = ' > ';
            elements.currentNodePath.appendChild(separator);
        }
    });
}

/**
 * 渲染节点编辑器
 */
function renderNodeEditor() {
    elements.nodeEditor.innerHTML = '';
    
    if (currentNodePath.length === 0) {
        elements.nodeEditor.innerHTML = '<div class="alert alert-info">请从左侧选择一个节点进行编辑</div>';
        return;
    }
    
    // 获取当前节点的值
    const nodeValue = getNodeValueByPath(scriptData, currentNodePath);
    
    if (nodeValue === undefined) {
        elements.nodeEditor.innerHTML = '<div class="alert alert-danger">无法找到选中的节点</div>';
        return;
    }
    
    const nodeType = getValueType(nodeValue);
    
    // 根据节点类型创建不同的编辑器
    switch (nodeType) {
        case 'string':
            createStringEditor(nodeValue);
            break;
        case 'number':
            createNumberEditor(nodeValue);
            break;
        case 'boolean':
            createBooleanEditor(nodeValue);
            break;
        case 'array':
            createArrayEditor(nodeValue);
            break;
        case 'object':
            createObjectEditor(nodeValue);
            break;
        default:
            elements.nodeEditor.innerHTML = '<div class="alert alert-warning">不支持编辑此类型的节点</div>';
    }
}

/**
 * 创建字符串编辑器
 * @param {string} value - 字符串值
 */
function createStringEditor(value) {
    const formGroup = document.createElement('div');
    formGroup.className = 'mb-3';
    
    const label = document.createElement('label');
    label.className = 'form-label';
    label.textContent = '文本值';
    
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'form-control';
    input.value = value;
    input.addEventListener('change', () => {
        updateNodeValue(input.value);
    });
    
    formGroup.appendChild(label);
    formGroup.appendChild(input);
    elements.nodeEditor.appendChild(formGroup);
}

/**
 * 创建数字编辑器
 * @param {number} value - 数字值
 */
function createNumberEditor(value) {
    const formGroup = document.createElement('div');
    formGroup.className = 'mb-3';
    
    const label = document.createElement('label');
    label.className = 'form-label';
    label.textContent = '数字值';
    
    const input = document.createElement('input');
    input.type = 'number';
    input.className = 'form-control';
    input.value = value;
    input.addEventListener('change', () => {
        updateNodeValue(parseFloat(input.value));
    });
    
    formGroup.appendChild(label);
    formGroup.appendChild(input);
    elements.nodeEditor.appendChild(formGroup);
}

/**
 * 创建布尔值编辑器
 * @param {boolean} value - 布尔值
 */
function createBooleanEditor(value) {
    const formGroup = document.createElement('div');
    formGroup.className = 'mb-3';
    
    const label = document.createElement('label');
    label.className = 'form-label';
    label.textContent = '布尔值';
    
    const select = document.createElement('select');
    select.className = 'form-select';
    
    const trueOption = document.createElement('option');
    trueOption.value = 'true';
    trueOption.textContent = '是 (true)';
    trueOption.selected = value === true;
    
    const falseOption = document.createElement('option');
    falseOption.value = 'false';
    falseOption.textContent = '否 (false)';
    falseOption.selected = value === false;
    
    select.appendChild(trueOption);
    select.appendChild(falseOption);
    
    select.addEventListener('change', () => {
        updateNodeValue(select.value === 'true');
    });
    
    formGroup.appendChild(label);
    formGroup.appendChild(select);
    elements.nodeEditor.appendChild(formGroup);
}

/**
 * 创建数组编辑器
 * @param {Array} value - 数组值
 */
function createArrayEditor(value) {
    const container = document.createElement('div');
    
    // 数组项容器
    const itemsContainer = document.createElement('div');
    itemsContainer.className = 'array-items';
    
    // 渲染数组项
    value.forEach((item, index) => {
        const itemContainer = document.createElement('div');
        itemContainer.className = 'form-array-item';
        
        // 删除按钮
        const removeBtn = document.createElement('button');
        removeBtn.className = 'btn btn-sm btn-danger remove-item';
        removeBtn.innerHTML = '<i class="bi bi-x"></i>';
        removeBtn.title = '删除项目';
        removeBtn.addEventListener('click', () => {
            removeArrayItem(index);
        });
        
        // 项目内容
        const itemContent = document.createElement('div');
        itemContent.className = 'item-content';
        
        // 根据项目类型创建不同的编辑器
        const itemType = getValueType(item);
        
        switch (itemType) {
            case 'string':
                const stringInput = document.createElement('input');
                stringInput.type = 'text';
                stringInput.className = 'form-control';
                stringInput.value = item;
                stringInput.dataset.index = index;
                stringInput.addEventListener('change', (e) => {
                    updateArrayItem(parseInt(e.target.dataset.index), e.target.value);
                });
                itemContent.appendChild(stringInput);
                break;
                
            case 'number':
                const numberInput = document.createElement('input');
                numberInput.type = 'number';
                numberInput.className = 'form-control';
                numberInput.value = item;
                numberInput.dataset.index = index;
                numberInput.addEventListener('change', (e) => {
                    updateArrayItem(parseInt(e.target.dataset.index), parseFloat(e.target.value));
                });
                itemContent.appendChild(numberInput);
                break;
                
            case 'boolean':
                const select = document.createElement('select');
                select.className = 'form-select';
                select.dataset.index = index;
                
                const trueOption = document.createElement('option');
                trueOption.value = 'true';
                trueOption.textContent = '是 (true)';
                trueOption.selected = item === true;
                
                const falseOption = document.createElement('option');
                falseOption.value = 'false';
                falseOption.textContent = '否 (false)';
                falseOption.selected = item === false;
                
                select.appendChild(trueOption);
                select.appendChild(falseOption);
                
                select.addEventListener('change', (e) => {
                    updateArrayItem(parseInt(e.target.dataset.index), e.target.value === 'true');
                });
                
                itemContent.appendChild(select);
                break;
                
            case 'object':
            case 'array':
                // 对于复杂类型，显示一个链接，点击后导航到该节点
                const complexLink = document.createElement('button');
                complexLink.className = 'btn btn-outline-primary';
                complexLink.textContent = `编辑 ${itemType === 'object' ? '对象' : '数组'} [${index}]`;
                complexLink.dataset.index = index;
                complexLink.addEventListener('click', (e) => {
                    const newPath = [...currentNodePath, parseInt(e.target.dataset.index)];
                    selectNode(newPath);
                });
                itemContent.appendChild(complexLink);
                break;
        }
        
        itemContainer.appendChild(removeBtn);
        itemContainer.appendChild(itemContent);
        itemsContainer.appendChild(itemContainer);
    });
    
    container.appendChild(itemsContainer);
    
    // 添加新项按钮
    const addControls = document.createElement('div');
    addControls.className = 'form-array-controls';
    
    const addBtn = document.createElement('button');
    addBtn.className = 'btn btn-success';
    addBtn.innerHTML = '<i class="bi bi-plus"></i> 添加项目';
    addBtn.addEventListener('click', () => {
        showAddArrayItemModal();
    });
    
    addControls.appendChild(addBtn);
    container.appendChild(addControls);
    
    elements.nodeEditor.appendChild(container);
}

/**
 * 创建对象编辑器
 * @param {Object} value - 对象值
 */
function createObjectEditor(value) {
    const container = document.createElement('div');
    
    // 对象属性列表
    const propertiesList = document.createElement('div');
    propertiesList.className = 'list-group mb-3';
    
    // 渲染对象属性
    for (const key in value) {
        const propertyItem = document.createElement('div');
        propertyItem.className = 'list-group-item d-flex justify-content-between align-items-center';
        
        // 属性名
        const propertyName = document.createElement('span');
        propertyName.textContent = key;
        
        // 属性值类型
        const propertyType = getValueType(value[key]);
        const typeLabel = document.createElement('span');
        typeLabel.className = `badge bg-${getTypeBadgeColor(propertyType)}`;
        typeLabel.textContent = getTypeDisplayName(propertyType);
        
        // 编辑按钮
        const editBtn = document.createElement('button');
        editBtn.className = 'btn btn-sm btn-outline-primary';
        editBtn.textContent = '编辑';
        editBtn.dataset.key = key;
        editBtn.addEventListener('click', (e) => {
            const newPath = [...currentNodePath, e.target.dataset.key];
            selectNode(newPath);
        });
        
        const btnGroup = document.createElement('div');
        btnGroup.appendChild(typeLabel);
        btnGroup.appendChild(document.createTextNode(' '));
        btnGroup.appendChild(editBtn);
        
        propertyItem.appendChild(propertyName);
        propertyItem.appendChild(btnGroup);
        propertiesList.appendChild(propertyItem);
    }
    
    container.appendChild(propertiesList);
    
    elements.nodeEditor.appendChild(container);
}

/**
 * 显示添加数组项模态框
 */
function showAddArrayItemModal() {
    // 重置表单
    elements.newItemKey.value = '';
    elements.newItemType.value = 'string';
    elements.newItemValue.value = '';
    elements.newItemKey.parentElement.style.display = 'none'; // 隐藏键名输入框
    
    // 显示模态框
    elements.addItemModal.show();
    
    // 设置确认按钮事件
    elements.confirmAddItem.onclick = () => {
        const type = elements.newItemType.value;
        let value = elements.newItemValue.value;
        
        // 根据类型转换值
        switch (type) {
            case 'number':
                value = parseFloat(value);
                break;
            case 'boolean':
                value = value === 'true';
                break;
            case 'object':
                value = {};
                break;
            case 'array':
                value = [];
                break;
        }
        
        // 添加到数组
        addArrayItem(value);
        
        // 关闭模态框
        elements.addItemModal.hide();
    };
}

/**
 * 显示添加项目模态框
 */
function showAddItemModal() {
    // 获取当前节点的值
    const nodeValue = getNodeValueByPath(scriptData, currentNodePath);
    
    if (!nodeValue) return;
    
    const nodeType = getValueType(nodeValue);
    
    // 只有对象和数组可以添加项目
    if (nodeType !== 'object' && nodeType !== 'array') {
        showAlert('错误', '只能向对象或数组添加项目');
        return;
    }
    
    // 重置表单
    elements.newItemKey.value = '';
    elements.newItemType.value = 'string';
    elements.newItemValue.value = '';
    
    // 对于对象，显示键名输入框；对于数组，隐藏键名输入框
    elements.newItemKey.parentElement.style.display = nodeType === 'object' ? 'block' : 'none';
    
    // 显示模态框
    elements.addItemModal.show();
    
    // 设置确认按钮事件
    elements.confirmAddItem.onclick = () => {
        const type = elements.newItemType.value;
        let value = elements.newItemValue.value;
        
        // 根据类型转换值
        switch (type) {
            case 'number':
                value = parseFloat(value);
                break;
            case 'boolean':
                value = value === 'true';
                break;
            case 'object':
                value = {};
                break;
            case 'array':
                value = [];
                break;
        }
        
        if (nodeType === 'object') {
            const key = elements.newItemKey.value.trim();
            
            if (!key) {
                showAlert('错误', '键名不能为空');
                return;
            }
            
            // 添加到对象
            addObjectProperty(key, value);
        } else {
            // 添加到数组
            addArrayItem(value);
        }
        
        // 关闭模态框
        elements.addItemModal.hide();
    };
}

/**
 * 切换新项目值输入框
 */
function toggleNewItemValueInput() {
    const type = elements.newItemType.value;
    
    // 对于对象和数组类型，隐藏值输入框
    if (type === 'object' || type === 'array') {
        elements.newItemValueContainer.style.display = 'none';
    } else {
        elements.newItemValueContainer.style.display = 'block';
        
        // 根据类型调整输入框
        if (type === 'boolean') {
            // 为布尔值创建下拉选择
            const select = document.createElement('select');
            select.className = 'form-select';
            select.id = 'newItemValue';
            
            const trueOption = document.createElement('option');
            trueOption.value = 'true';
            trueOption.textContent = '是 (true)';
            
            const falseOption = document.createElement('option');
            falseOption.value = 'false';
            falseOption.textContent = '否 (false)';
            
            select.appendChild(trueOption);
            select.appendChild(falseOption);
            
            // 替换输入框
            const container = elements.newItemValueContainer;
            const oldInput = document.getElementById('newItemValue');
            container.replaceChild(select, oldInput);
            elements.newItemValue = select;
        } else {
            // 为字符串和数字创建文本输入框
            const input = document.createElement('input');
            input.type = type === 'number' ? 'number' : 'text';
            input.className = 'form-control';
            input.id = 'newItemValue';
            
            // 替换输入框
            const container = elements.newItemValueContainer;
            const oldInput = document.getElementById('newItemValue');
            if (oldInput.tagName !== 'INPUT') {
                container.replaceChild(input, oldInput);
                elements.newItemValue = input;
            } else {
                oldInput.type = type === 'number' ? 'number' : 'text';
            }
        }
    }
}

/**
 * 处理添加项目
 */
function handleAddItem() {
    // 这个函数是一个占位符，实际的添加逻辑在showAddItemModal中设置
}

/**
 * 处理删除项目
 */
function handleDeleteItem() {
    if (currentNodePath.length === 0) {
        showAlert('错误', '请先选择一个节点');
        return;
    }
    
    // 不允许删除顶级必需节点
    if (currentNodePath.length === 1 && requiredNodes.includes(currentNodePath[0])) {
        showAlert('错误', '不能删除必需的节点');
        return;
    }
    
    // 确认删除
    if (confirm(`确定要删除节点 "${currentNodePath[currentNodePath.length - 1]}" 吗？`)) {
        deleteNode();
    }
}

/**
 * 删除当前选中的节点
 */
function deleteNode() {
    // 获取父节点路径和当前节点键
    const parentPath = currentNodePath.slice(0, -1);
    const nodeKey = currentNodePath[currentNodePath.length - 1];
    
    // 获取父节点值
    const parentValue = parentPath.length > 0 ? getNodeValueByPath(scriptData, parentPath) : scriptData;
    
    if (!parentValue) return;
    
    // 根据父节点类型删除节点
    if (Array.isArray(parentValue)) {
        // 从数组中删除
        parentValue.splice(nodeKey, 1);
    } else if (typeof parentValue === 'object') {
        // 从对象中删除
        delete parentValue[nodeKey];
    }
    
    // 保存到localStorage
    localStorage.setItem('scriptEditorData', JSON.stringify(scriptData));
    
    // 更新UI
    refreshUI();
    
    // 选择父节点
    selectNode(parentPath);
    
    showAlert('成功', '节点已删除');
}

/**
 * 添加对象属性
 * @param {string} key - 属性键名
 * @param {*} value - 属性值
 */
function addObjectProperty(key, value) {
    // 获取当前节点的值
    const nodeValue = getNodeValueByPath(scriptData, currentNodePath);
    
    if (!nodeValue || typeof nodeValue !== 'object' || Array.isArray(nodeValue)) return;
    
    // 检查键名是否已存在
    if (nodeValue.hasOwnProperty(key)) {
        showAlert('错误', `属性 "${key}" 已存在`);
        return;
    }
    
    // 添加属性
    nodeValue[key] = value;
    
    // 保存到localStorage
    localStorage.setItem('scriptEditorData', JSON.stringify(scriptData));
    
    // 更新UI
    refreshUI();
    
    // 选择新添加的节点
    selectNode([...currentNodePath, key]);
    
    showAlert('成功', `属性 "${key}" 已添加`);
}

/**
 * 添加数组项
 * @param {*} value - 项目值
 */
function addArrayItem(value) {
    // 获取当前节点的值
    const nodeValue = getNodeValueByPath(scriptData, currentNodePath);
    
    if (!nodeValue || !Array.isArray(nodeValue)) return;
    
    // 添加到数组
    nodeValue.push(value);
    
    // 保存到localStorage
    localStorage.setItem('scriptEditorData', JSON.stringify(scriptData));
    
    // 更新UI
    refreshUI();
    
    // 选择新添加的节点
    selectNode([...currentNodePath, nodeValue.length - 1]);
    
    showAlert('成功', '项目已添加');
}

/**
 * 更新数组项
 * @param {number} index - 项目索引
 * @param {*} value - 新值
 */
function updateArrayItem(index, value) {
    // 获取当前节点的值
    const nodeValue = getNodeValueByPath(scriptData, currentNodePath);
    
    if (!nodeValue || !Array.isArray(nodeValue) || index < 0 || index >= nodeValue.length) return;
    
    // 更新数组项
    nodeValue[index] = value;
    
    // 保存到localStorage
    localStorage.setItem('scriptEditorData', JSON.stringify(scriptData));
}

/**
 * 删除数组项
 * @param {number} index - 项目索引
 */
function removeArrayItem(index) {
    // 获取当前节点的值
    const nodeValue = getNodeValueByPath(scriptData, currentNodePath);
    
    if (!nodeValue || !Array.isArray(nodeValue) || index < 0 || index >= nodeValue.length) return;
    
    // 从数组中删除
    nodeValue.splice(index, 1);
    
    // 保存到localStorage
    localStorage.setItem('scriptEditorData', JSON.stringify(scriptData));
    
    // 更新UI
    renderNodeEditor();
    renderScriptTree();
    
    showAlert('成功', '项目已删除');
}

/**
 * 更新节点值
 * @param {*} newValue - 新值
 */
function updateNodeValue(newValue) {
    if (currentNodePath.length === 0) return;
    
    // 获取父节点路径和当前节点键
    const parentPath = currentNodePath.slice(0, -1);
    const nodeKey = currentNodePath[currentNodePath.length - 1];
    
    // 获取父节点值
    const parentValue = parentPath.length > 0 ? getNodeValueByPath(scriptData, parentPath) : scriptData;
    
    if (!parentValue) return;
    
    // 更新节点值
    if (Array.isArray(parentValue)) {
        parentValue[nodeKey] = newValue;
    } else if (typeof parentValue === 'object') {
        parentValue[nodeKey] = newValue;
    }
    
    // 保存到localStorage
    localStorage.setItem('scriptEditorData', JSON.stringify(scriptData));
    
    // 更新树形结构
    renderScriptTree();
}

/**
 * 根据路径获取节点值
 * @param {Object} data - 数据对象
 * @param {Array} path - 节点路径
 * @returns {*} 节点值
 */
function getNodeValueByPath(data, path) {
    if (!data || path.length === 0) return undefined;
    
    let value = data;
    
    for (const key of path) {
        if (value === undefined || value === null) return undefined;
        
        value = value[key];
    }
    
    return value;
}

/**
 * 获取值的类型
 * @param {*} value - 要检查的值
 * @returns {string} 类型名称
 */
function getValueType(value) {
    if (value === null) return 'null';
    if (Array.isArray(value)) return 'array';
    return typeof value;
}

/**
 * 获取类型的显示名称
 * @param {string} type - 类型名称
 * @returns {string} 显示名称
 */
function getTypeDisplayName(type) {
    const typeMap = {
        'string': '文本',
        'number': '数字',
        'boolean': '布尔',
        'object': '对象',
        'array': '数组',
        'null': 'null',
        'undefined': 'undefined'
    };
    
    return typeMap[type] || type;
}

/**
 * 获取类型的徽章颜色
 * @param {string} type - 类型名称
 * @returns {string} 颜色类名
 */
function getTypeBadgeColor(type) {
    const colorMap = {
        'string': 'danger',
        'number': 'warning',
        'boolean': 'secondary',
        'object': 'primary',
        'array': 'success',
        'null': 'light',
        'undefined': 'light'
    };
    
    return colorMap[type] || 'info';
}

/**
 * 显示警告框
 * @param {string} title - 标题
 * @param {string} message - 消息内容
 */
function showAlert(title, message) {
    elements.alertModalTitle.textContent = title;
    elements.alertModalBody.textContent = message;
    elements.alertModal.show();
}
