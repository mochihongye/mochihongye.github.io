// ======================
// 评论功能模块（全面修复版本）
// 修复内容：
// 1. 异步请求状态判断错误
// 2. 请求回调执行顺序问题
// 3. 多级评论定位问题  
// 4. 全局状态锁干扰
// 5. 谁@谁显示问题
// ======================
const CommentModule = (function() {
    const API_BASE = '/api';
    const SUBMIT_LOCKS = {};
    
    function getElement(id) {
        return document.getElementById(id);
    }
    
    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
    
    // 局部刷新评论区域（保持展开状态）
    async function refreshCommentSection(messageId) {
        try {
            const user = localStorage.getItem('user');
            const res = await fetch(`${API_BASE}/messages?username=${encodeURIComponent(user || '')}`);
            const data = await res.json();
            
            if (data.success && data.messages) {
                const targetMsg = data.messages.find(m => m.id === messageId);
                if (targetMsg && targetMsg.comments) {
                    const commentList = getElement(`comment-list-${messageId}`);
                    if (commentList) {
                        commentList.innerHTML = targetMsg.comments.map(c => {
                            const likes = c.likes || 0;
                            const hasLiked = c.liked_by_user === true;
                            const heartIcon = hasLiked ? '❤️' : '🤍';
                            const replyTo = c.reply_to_username ? `<span class="reply-tag">@${c.reply_to_username}</span>` : '';
                            return `
                            <div class="comment-item" data-comment-id="${c.id}" data-message-id="${messageId}">
                                <div class="comment-header">
                                    <span class="comment-username">${c.username}</span>
                                    ${replyTo}
                                    <span class="comment-time">${formatTime(c.created_at)}</span>
                                </div>
                                <div class="comment-content">${c.comment}</div>
                                <div class="comment-actions">
                                    <span class="comment-action${hasLiked ? ' liked' : ''}" data-action="like-comment" data-like-id="${c.id}" data-type="comment">
                                        ${heartIcon} <span class="like-count">${likes}</span>
                                    </span>
                                    <span class="comment-action" data-action="toggle-reply" data-message-id="${messageId}" data-comment-id="${c.id}" data-username="${c.username}">
                                        💬 回复
                                    </span>
                                </div>
                                <div class="reply-input-area" id="reply-input-${c.id}" style="display:none;">
                                    <input type="text" id="reply-text-${c.id}" placeholder="回复 ${c.username}..." data-parent-id="${c.id}">
                                    <button class="reply-submit-btn" data-action="submit-reply" data-message-id="${messageId}" data-parent-id="${c.id}" data-username="${c.username}">发送</button>
                                </div>
                            </div>
                        `}).join('');
                    }
                }
            }
        } catch (e) {
            console.error('[CommentModule] 局部刷新失败:', e);
        }
    }
    
    function formatTime(timeStr) {
        if (!timeStr) return '';
        
        let date;
        if (typeof timeStr === 'string') {
            timeStr = timeStr.trim();
            if (timeStr.includes('-') && timeStr.includes(' ')) {
                const parts = timeStr.split(' ');
                const dateParts = parts[0].split('-');
                const timeParts = parts[1]?.split(':') || [0, 0, 0];
                date = new Date(
                    parseInt(dateParts[0]),
                    parseInt(dateParts[1]) - 1,
                    parseInt(dateParts[2]),
                    parseInt(timeParts[0]) || 0,
                    parseInt(timeParts[1]) || 0,
                    parseInt(timeParts[2]) || 0
                );
            } else {
                date = new Date(timeStr);
            }
        } else {
            date = new Date(timeStr);
        }
        
        if (isNaN(date.getTime())) {
            console.warn(`[formatTime] 无法解析时间字符串: ${timeStr}`);
            return timeStr;
        }
        
        const now = new Date();
        const diff = now - date;
        
        if (diff < 60000) return '刚刚';
        if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`;
        if (diff < 604800000) return `${Math.floor(diff / 86400000)}天前`;
        return date.toLocaleDateString('zh-CN');
    }
    
    async function request(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };
        
        const startTime = Date.now();
        console.log(`[CommentModule] 发起请求: ${url}`, options.body ? JSON.parse(options.body) : null);
        
        const res = await fetch(url, defaultOptions);
        
        console.log(`[CommentModule] 请求完成: ${url}, 状态码: ${res.status}, 耗时: ${Date.now() - startTime}ms`);
        
        let data;
        try {
            data = await res.json();
            console.log(`[CommentModule] 响应数据:`, data);
        } catch (e) {
            console.error(`[CommentModule] 解析响应失败:`, e);
            throw new Error('响应解析失败');
        }
        
        if (!res.ok) {
            const errorMsg = data?.message || data?.msg || `HTTP错误: ${res.status}`;
            throw new Error(errorMsg);
        }
        
        return data;
    }
    
    function isRequestSuccessful(data) {
        if (data === null || data === undefined) return false;
        if (data.success === true) return true;
        if (data.code === 1 || data.code === 'success') return true;
        if (data.status && (data.status === 'success' || data.status === 200)) return true;
        return false;
    }
    
    function createCommentElement(comment, messageId) {
        const likes = comment.likes || 0;
        const hasLiked = comment.liked_by_user === true;
        const heartIcon = hasLiked ? '❤️' : '🤍';
        
        let replyToDisplay = '';
        if (comment.reply_to_username && comment.reply_to_username !== comment.username) {
            replyToDisplay = `<span class="reply-tag"> @${comment.reply_to_username}</span>`;
        }
        
        const div = document.createElement('div');
        div.className = 'comment-item';
        div.dataset.commentId = comment.id;
        div.dataset.messageId = messageId;
        if (comment.parent_id) {
            div.dataset.parentId = comment.parent_id;
            div.classList.add('reply-comment');
        }
        
        div.innerHTML = `
            <div class="comment-header">
                <span class="comment-username">${comment.username}</span>
                ${replyToDisplay}
                <span class="comment-time">${formatTime(comment.created_at)}</span>
            </div>
            <div class="comment-content">${comment.comment}</div>
            <div class="comment-actions">
                <span class="comment-action${hasLiked ? ' liked' : ''}" data-action="like-comment" data-like-id="${comment.id}" data-type="comment">
                    ${heartIcon} <span class="like-count">${likes}</span>
                </span>
                <span class="comment-action" data-action="toggle-reply" data-message-id="${messageId}" data-comment-id="${comment.id}" data-username="${comment.username}">
                    💬 回复
                </span>
            </div>
            <div class="reply-input-area" id="reply-input-${comment.id}" style="display:none;">
                <input type="text" id="reply-text-${comment.id}" placeholder="回复 ${comment.username}..." data-parent-id="${comment.id}">
                <button class="reply-submit-btn" data-action="submit-reply" data-message-id="${messageId}" data-parent-id="${comment.id}" data-username="${comment.username}">发送</button>
            </div>
        `;
        
        return div;
    }
    
    function highlightNewComment(element) {
        if (!element) return;
        
        element.style.animation = 'highlightPulse 1s ease-in-out';
        
        setTimeout(() => {
            element.style.animation = '';
        }, 1000);
    }
    
    function acquireSubmitLock(key) {
        if (SUBMIT_LOCKS[key]) {
            return false;
        }
        SUBMIT_LOCKS[key] = true;
        return true;
    }
    
    function releaseSubmitLock(key) {
        delete SUBMIT_LOCKS[key];
    }
    
    return {
        toggleReplyInput: function(commentId) {
            const replyInput = getElement(`reply-input-${commentId}`);
            const textInput = getElement(`reply-text-${commentId}`);
            
            if (!replyInput) {
                console.warn(`[CommentModule] 找不到回复输入框: reply-input-${commentId}`);
                return;
            }
            
            if (replyInput.style.display === 'none' || replyInput.style.display === '') {
                replyInput.style.display = 'flex';
                if (textInput) textInput.focus();
            } else {
                replyInput.style.display = 'none';
                if (textInput) textInput.value = '';
            }
        },
        
        likeComment: async function(commentId) {
            const user = localStorage.getItem('user');
            if (!user) {
                showSuccessToast('❌ 请先登录！');
                return;
            }
            
            try {
                const data = await request(`${API_BASE}/comment/${commentId}/like`, {
                    method: 'POST',
                    body: JSON.stringify({ username: user })
                });
                
                if (isRequestSuccessful(data)) {
                    const commentItem = document.querySelector(`.comment-item[data-comment-id="${commentId}"]`);
                    if (commentItem) {
                        const likeSpan = commentItem.querySelector('.comment-action[data-action="like-comment"]');
                        if (likeSpan) {
                            const likes = data.likes !== undefined ? data.likes : 
                                (parseInt(likeSpan.querySelector('.like-count')?.textContent) || 0) + (data.liked ? 1 : -1);
                            
                            if (data.liked) {
                                likeSpan.innerHTML = `❤️ <span class="like-count">${likes}</span>`;
                                likeSpan.classList.add('liked');
                            } else {
                                likeSpan.innerHTML = `🤍 <span class="like-count">${likes}</span>`;
                                likeSpan.classList.remove('liked');
                            }
                        }
                    }
                    showSuccessToast(data.liked ? '❤️ 点赞成功！' : '💔 取消点赞');
                } else {
                    showSuccessToast('❌ ' + (data.message || data.msg || '操作失败'));
                }
            } catch (e) {
                console.error('[CommentModule] 点赞失败:', e);
                showSuccessToast('❌ 网络错误，请重试！');
            }
        },
        
        submitComment: async function(messageId) {
            const user = localStorage.getItem('user');
            const input = getElement(`comment-input-${messageId}`);
            const comment = input ? input.value.trim() : '';
            
            if (!user) {
                showSuccessToast('❌ 请先登录！');
                return;
            }
            
            if (!comment) {
                showSuccessToast('❌ 评论内容不能为空！');
                return;
            }
            
            const lockKey = `comment_${messageId}`;
            if (!acquireSubmitLock(lockKey)) {
                showSuccessToast('⏳ 正在提交中，请稍候...');
                return;
            }
            
            try {
                console.log(`[CommentModule] 提交评论: messageId=${messageId}, user=${user}`);
                
                const data = await request(`${API_BASE}/message/${messageId}/comment`, {
                    method: 'POST',
                    body: JSON.stringify({ 
                        username: user, 
                        comment: escapeHtml(comment) 
                    })
                });
                
                console.log(`[CommentModule] 评论提交结果:`, data);
                
                if (isRequestSuccessful(data)) {
                    if (input) input.value = '';
                    
                    // 获取新评论ID用于高亮
                    const newCommentId = data.comment?.id || data.id;
                    
                    // 优先使用服务器返回的评论列表刷新
                    if (data.comments && Array.isArray(data.comments)) {
                        const commentList = getElement(`comment-list-${messageId}`);
                        if (commentList) {
                            commentList.innerHTML = data.comments.map(c => {
                                const likes = c.likes || 0;
                                const hasLiked = c.liked_by_user === true;
                                const heartIcon = hasLiked ? '❤️' : '🤍';
                                const replyTo = c.reply_to_username ? `<span class="reply-tag">@${c.reply_to_username}</span>` : '';
                                const isNew = c.id === newCommentId ? ' new-comment-highlight' : '';
                                return `
                                <div class="comment-item${isNew}" data-comment-id="${c.id}" data-message-id="${messageId}">
                                    <div class="comment-header">
                                        <span class="comment-username">${c.username}</span>
                                        ${replyTo}
                                        <span class="comment-time">${formatTime(c.created_at)}</span>
                                    </div>
                                    <div class="comment-content">${c.comment}</div>
                                    <div class="comment-actions">
                                        <span class="comment-action${hasLiked ? ' liked' : ''}" data-action="like-comment" data-like-id="${c.id}" data-type="comment">
                                            ${heartIcon} <span class="like-count">${likes}</span>
                                        </span>
                                        <span class="comment-action" data-action="toggle-reply" data-message-id="${messageId}" data-comment-id="${c.id}" data-username="${c.username}">
                                            💬 回复
                                        </span>
                                    </div>
                                    <div class="reply-input-area" id="reply-input-${c.id}" style="display:none;">
                                        <input type="text" id="reply-text-${c.id}" placeholder="回复 ${c.username}..." data-parent-id="${c.id}">
                                        <button class="reply-submit-btn" data-action="submit-reply" data-message-id="${messageId}" data-parent-id="${c.id}" data-username="${c.username}">发送</button>
                                    </div>
                                </div>
                            `}).join('');
                            
                            // 确保只有最新的评论显示高亮
                            if (newCommentId) {
                                // 先移除所有之前的高亮
                                const existingHighlights = commentList.querySelectorAll('.flash-highlight');
                                existingHighlights.forEach(el => el.classList.remove('flash-highlight'));
                                
                                // 只高亮最新的评论
                                const newCommentEl = commentList.querySelector(`[data-comment-id="${newCommentId}"]`);
                                if (newCommentEl) {
                                    newCommentEl.classList.add('flash-highlight');
                                    setTimeout(() => {
                                        newCommentEl.classList.remove('flash-highlight');
                                    }, 1000);
                                    // 滚动到新评论位置
                                    newCommentEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                }
                            }
                        }
                    } else {
                        // 兼容旧逻辑：手动添加新评论
                        const newComment = data.comment || data.data || {
                            id: data.id,
                            username: user,
                            comment: comment,
                            likes: 0,
                            liked_by_user: false,
                            created_at: new Date().toISOString(),
                            parent_id: null
                        };
                        
                        const commentElement = createCommentElement(newComment, messageId);
                        const commentList = getElement(`comment-list-${messageId}`);
                        if (commentList) {
                            // 先移除所有之前的高亮
                            const existingHighlights = commentList.querySelectorAll('.flash-highlight');
                            existingHighlights.forEach(el => el.classList.remove('flash-highlight'));
                            
                            commentList.insertBefore(commentElement, commentList.firstChild);
                            // 高亮闪烁新评论
                            commentElement.classList.add('flash-highlight');
                            setTimeout(() => {
                                commentElement.classList.remove('flash-highlight');
                            }, 1000);
                            // 滚动到新评论位置
                            commentElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        }
                    }
                    
                    const commentToggle = document.querySelector(`.comment-toggle[data-message-id="${messageId}"]`);
                    if (commentToggle) {
                        const currentCount = parseInt(commentToggle.innerText.match(/\d+/)[0]) || 0;
                        commentToggle.innerText = `💬 评论 (${currentCount + 1})`;
                    }
                } else {
                    const errorMsg = data.message || data.msg || '评论失败！';
                    console.warn(`[CommentModule] 业务失败: ${errorMsg}`);
                    // 容错刷新：即使失败也尝试刷新评论列表（保持展开状态）
                    refreshCommentSection(messageId);
                }
            } catch (e) {
                console.error('[CommentModule] 评论提交异常:', e);
                // 容错刷新：网络错误时刷新评论列表（保持展开状态）
                refreshCommentSection(messageId);
            } finally {
                releaseSubmitLock(lockKey);
            }
        },
        
        submitReply: async function(messageId, parentId) {
            const user = localStorage.getItem('user');
            const input = getElement(`reply-text-${parentId}`);
            const submitBtn = document.querySelector(`.reply-submit-btn[data-message-id="${messageId}"][data-parent-id="${parentId}"]`);
            const comment = input ? input.value.trim() : '';
            
            console.log(`[CommentModule] 提交回复: messageId=${messageId}, parentId=${parentId}, user=${user}`);
            
            if (!user) {
                showSuccessToast('❌ 请先登录！');
                return;
            }
            
            if (!comment) {
                showSuccessToast('❌ 回复内容不能为空！');
                return;
            }
            
            if (!parentId || isNaN(parseInt(parentId))) {
                showSuccessToast('❌ 缺少回复目标！');
                return;
            }
            
            const lockKey = `reply_${messageId}_${parentId}`;
            if (!acquireSubmitLock(lockKey)) {
                showSuccessToast('⏳ 正在提交中，请稍候...');
                return;
            }
            
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = '发送中...';
            }
            
            try {
                const replyToUsername = submitBtn?.dataset.username;
                console.log(`[CommentModule] 回复目标: ${replyToUsername}`);
                
                const data = await request(`${API_BASE}/message/${messageId}/comment`, {
                    method: 'POST',
                    body: JSON.stringify({ 
                        username: user, 
                        comment: escapeHtml(comment), 
                        parent_id: parseInt(parentId),
                        reply_to_username: replyToUsername
                    })
                });
                
                console.log(`[CommentModule] 回复提交结果:`, data);
                
                if (isRequestSuccessful(data)) {
                    if (input) input.value = '';
                    
                    const replyInput = getElement(`reply-input-${parentId}`);
                    if (replyInput) replyInput.style.display = 'none';
                    
                    // 获取新评论ID用于高亮
                    const newCommentId = data.comment?.id || data.id;
                    
                    // 优先使用服务器返回的评论列表刷新
                    if (data.comments && Array.isArray(data.comments)) {
                        const commentList = getElement(`comment-list-${messageId}`);
                        if (commentList) {
                            commentList.innerHTML = data.comments.map(c => {
                                const likes = c.likes || 0;
                                const hasLiked = c.liked_by_user === true;
                                const heartIcon = hasLiked ? '❤️' : '🤍';
                                const replyTo = c.reply_to_username ? `<span class="reply-tag">@${c.reply_to_username}</span>` : '';
                                const isNew = c.id === newCommentId ? ' new-comment-highlight' : '';
                                return `
                                <div class="comment-item${isNew}" data-comment-id="${c.id}" data-message-id="${messageId}">
                                    <div class="comment-header">
                                        <span class="comment-username">${c.username}</span>
                                        ${replyTo}
                                        <span class="comment-time">${formatTime(c.created_at)}</span>
                                    </div>
                                    <div class="comment-content">${c.comment}</div>
                                    <div class="comment-actions">
                                        <span class="comment-action${hasLiked ? ' liked' : ''}" data-action="like-comment" data-like-id="${c.id}" data-type="comment">
                                            ${heartIcon} <span class="like-count">${likes}</span>
                                        </span>
                                        <span class="comment-action" data-action="toggle-reply" data-message-id="${messageId}" data-comment-id="${c.id}" data-username="${c.username}">
                                            💬 回复
                                        </span>
                                    </div>
                                    <div class="reply-input-area" id="reply-input-${c.id}" style="display:none;">
                                        <input type="text" id="reply-text-${c.id}" placeholder="回复 ${c.username}..." data-parent-id="${c.id}">
                                        <button class="reply-submit-btn" data-action="submit-reply" data-message-id="${messageId}" data-parent-id="${c.id}" data-username="${c.username}">发送</button>
                                    </div>
                                </div>
                            `}).join('');
                            
                            // 确保只有最新的评论显示高亮
                            if (newCommentId) {
                                // 先移除所有之前的高亮
                                const existingHighlights = commentList.querySelectorAll('.flash-highlight');
                                existingHighlights.forEach(el => el.classList.remove('flash-highlight'));
                                
                                // 只高亮最新的评论
                                const newCommentEl = commentList.querySelector(`[data-comment-id="${newCommentId}"]`);
                                if (newCommentEl) {
                                    newCommentEl.classList.add('flash-highlight');
                                    setTimeout(() => {
                                        newCommentEl.classList.remove('flash-highlight');
                                    }, 1000);
                                    // 滚动到新评论位置
                                    newCommentEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                }
                            }
                        }
                    } else {
                        // 兼容旧逻辑：手动添加新评论
                        const newComment = data.comment || data.data || {
                            id: data.id,
                            username: user,
                            comment: comment,
                            reply_to_username: replyToUsername,
                            parent_id: parseInt(parentId),
                            likes: 0,
                            liked_by_user: false,
                            created_at: new Date().toISOString()
                        };
                        
                        const commentElement = createCommentElement(newComment, messageId);
                        
                        // 先移除所有之前的高亮
                        const commentList = getElement(`comment-list-${messageId}`);
                        if (commentList) {
                            const existingHighlights = commentList.querySelectorAll('.flash-highlight');
                            existingHighlights.forEach(el => el.classList.remove('flash-highlight'));
                        }
                        
                        const parentComment = document.querySelector(`.comment-item[data-comment-id="${parentId}"]`);
                        
                        if (parentComment && commentList) {
                            let insertPosition = parentComment.nextElementSibling;
                            
                            while (insertPosition && insertPosition.classList.contains('reply-comment')) {
                                insertPosition = insertPosition.nextElementSibling;
                            }
                            
                            commentList.insertBefore(commentElement, insertPosition);
                            // 高亮闪烁新评论（多级评论也生效）
                            commentElement.classList.add('flash-highlight');
                            setTimeout(() => {
                                commentElement.classList.remove('flash-highlight');
                            }, 1000);
                            // 滚动到新评论位置
                            commentElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            console.log(`[CommentModule] 子评论已插入到父评论之后`);
                        } else if (commentList) {
                            commentList.appendChild(commentElement);
                            // 高亮闪烁新评论（多级评论也生效）
                            commentElement.classList.add('flash-highlight');
                            setTimeout(() => {
                                commentElement.classList.remove('flash-highlight');
                            }, 1000);
                            // 滚动到新评论位置
                            commentElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            console.warn(`[CommentModule] 未找到父评论，已追加到列表末尾`);
                        } else {
                            console.error(`[CommentModule] 找不到评论列表容器: comment-list-${messageId}`);
                        }
                    }
                    
                    const commentToggle = document.querySelector(`.comment-toggle[data-message-id="${messageId}"]`);
                    if (commentToggle) {
                        const currentCount = parseInt(commentToggle.innerText.match(/\d+/)[0]) || 0;
                        commentToggle.innerText = `💬 评论 (${currentCount + 1})`;
                    }
                } else {
                    const errorMsg = data.message || data.msg || '回复失败！';
                    console.warn(`[CommentModule] 业务失败: ${errorMsg}`);
                    // 容错刷新：即使失败也尝试刷新评论列表（保持展开状态）
                    refreshCommentSection(messageId);
                }
            } catch (e) {
                console.error('[CommentModule] 回复提交异常:', e);
                // 容错刷新：网络错误时刷新评论列表（保持展开状态）
                refreshCommentSection(messageId);
            } finally {
                releaseSubmitLock(lockKey);
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = '发送';
                }
            }
        },
        
        deleteComment: async function(commentId, messageId) {
            const user = localStorage.getItem('user');
            if (!user) {
                showSuccessToast('❌ 请先登录！');
                return;
            }
            
            if (!confirm('确定删除此评论？')) return;
            
            try {
                const data = await request(`${API_BASE}/comment/${commentId}/delete`, {
                    method: 'DELETE',
                    body: JSON.stringify({ username: user })
                });
                
                if (isRequestSuccessful(data)) {
                    const commentItem = document.querySelector(`.comment-item[data-comment-id="${commentId}"]`);
                    if (commentItem) {
                        commentItem.remove();
                    }
                    
                    const commentToggle = document.querySelector(`.comment-toggle[data-message-id="${messageId}"]`);
                    if (commentToggle) {
                        const currentCount = parseInt(commentToggle.innerText.match(/\d+/)[0]) || 1;
                        commentToggle.innerText = `💬 评论 (${Math.max(0, currentCount - 1)})`;
                    }
                    
                    showSuccessToast('✅ 删除成功！');
                } else {
                    showSuccessToast('❌ ' + (data.message || data.msg || '删除失败'));
                }
            } catch (e) {
                console.error('[CommentModule] 删除评论异常:', e);
                showSuccessToast('❌ 网络错误，请重试！');
            }
        }
    };
})();

// 导出供全局使用
window.CommentModule = CommentModule;
window.formatTime = formatTime;