#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
哈基米网站后端服务
使用 Flask + MySQL 连接网页前端

数据库表结构：
1. users - 用户表（账号密码、等级、经验、小鱼干）
2. messages - 留言表
3. game_scores - 游戏成绩表
4. achievements - 成就表

运行方式：
1. 安装依赖：pip install flask flask-cors pymysql
2. 修改数据库配置
3. 运行：python app.py
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import pymysql
import hashlib
import datetime
import os
import decimal

app = Flask(__name__, static_folder='.', static_url_path='')
app.json.sort_keys = False
CORS(app)

# 自定义JSON序列化
from flask.json.provider import DefaultJSONProvider
class CustomJSONProvider(DefaultJSONProvider):
    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        return super().default(obj)

app.json_provider_class = CustomJSONProvider

# ====================
# 数据库配置
# ====================
DB_CONFIG = {
    'host': 'localhost',           # 数据库地址
    'port': 3306,                  # 端口
    'user': 'user',                # 用户名
    'password': 'Liuyuhang0813',   # 密码
    'database': 'hjm',             # 数据库名
    'charset': 'utf8mb4'
}

# ====================
# 数据库连接工具
# ====================
def get_db_connection():
    """获取数据库连接"""
    return pymysql.connect(**DB_CONFIG)

def init_database():
    """初始化数据库表（首次运行时执行）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 创建用户表（只存账号密码）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            is_admin TINYINT(1) DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login DATETIME NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    ''')
    
    # 创建用户属性表（经验、等级、小鱼干）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_stats (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            level INT DEFAULT 0,
            exp INT DEFAULT 0,
            fish INT DEFAULT 10,
            sign_days INT DEFAULT 0,
            last_sign DATETIME NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    ''')
    
    # 创建留言表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) NOT NULL,
            message TEXT NOT NULL,
            likes INT DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    ''')
    
    # 创建评论表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            message_id INT NOT NULL,
            parent_id INT NULL,
            username VARCHAR(50) NOT NULL,
            reply_to_username VARCHAR(50) NULL,
            comment TEXT NOT NULL,
            likes INT DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE,
            FOREIGN KEY (parent_id) REFERENCES comments(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    ''')
    
    try:
        cursor.execute('''
            ALTER TABLE comments ADD COLUMN reply_to_username VARCHAR(50) NULL;
        ''')
        conn.commit()
    except Exception:
        pass
    
    # 添加索引优化查询性能
    try:
        cursor.execute('ALTER TABLE comments ADD INDEX idx_parent_id (parent_id)')
        conn.commit()
    except Exception:
        pass
    
    try:
        cursor.execute('ALTER TABLE comments ADD INDEX idx_message_id (message_id)')
        conn.commit()
    except Exception:
        pass
    
    try:
        cursor.execute('ALTER TABLE comments ADD INDEX idx_created_at (created_at)')
        conn.commit()
    except Exception:
        pass
    
    # 创建消息通知表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INT AUTO_INCREMENT PRIMARY KEY,
            target_user VARCHAR(50) NOT NULL,
            type VARCHAR(20) NOT NULL,
            source_user VARCHAR(50) NOT NULL,
            message_id INT NULL,
            comment_id INT NULL,
            content TEXT NOT NULL,
            is_read BOOLEAN DEFAULT FALSE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    ''')
    
    # 创建点赞记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS message_likes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            message_id INT NOT NULL,
            username VARCHAR(50) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY idx_message_user (message_id, username),
            FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    ''')
    
    # 创建游戏成绩表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS game_scores (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) NOT NULL,
            game_name VARCHAR(50) NOT NULL,
            score INT DEFAULT 0,
            score_type VARCHAR(20) DEFAULT 'score',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY idx_user_game (username, game_name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    ''')
    
    # 创建成就表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS achievements (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) NOT NULL,
            achievement_id VARCHAR(50) NOT NULL,
            unlocked TINYINT(1) DEFAULT 0,
            unlocked_at DATETIME NULL,
            UNIQUE KEY idx_user_achievement (username, achievement_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    ''')
    
    # 数据库迁移：为已有messages表添加likes字段
    try:
        cursor.execute("ALTER TABLE messages ADD COLUMN likes INT DEFAULT 0")
        print("✅ 已为messages表添加likes字段")
    except Exception as e:
        # 字段已存在，忽略错误
        pass
    
    # 数据库迁移：为已有users表添加last_login字段
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN last_login DATETIME NULL")
        print("✅ 已为users表添加last_login字段")
    except Exception as e:
        # 字段已存在，忽略错误
        pass
    
    # 数据库迁移：为已有comments表添加parent_id和likes字段
    try:
        cursor.execute("ALTER TABLE comments ADD COLUMN parent_id INT NULL")
        cursor.execute("ALTER TABLE comments ADD COLUMN likes INT DEFAULT 0")
        print("✅ 已为comments表添加parent_id和likes字段")
    except Exception as e:
        # 字段已存在，忽略错误
        pass
    
    conn.commit()
    
    # 初始化默认管理员账号
    admin_username = '哈基米创造神'
    admin_password = 'admin123'
    try:
        cursor.execute('SELECT username FROM users WHERE username = %s', (admin_username,))
        if not cursor.fetchone():
            cursor.execute(
                'INSERT INTO users (username, password, is_admin) VALUES (%s, %s, 1)',
                (admin_username, hash_password(admin_password))
            )
            cursor.execute(
                'INSERT INTO user_stats (username, level, exp, fish) VALUES (%s, 999, 999999, 999999)',
                (admin_username,)
            )
            conn.commit()
            print("✅ 默认管理员账号已创建 (哈基米创造神/admin123)")
        else:
            cursor.execute(
                'UPDATE users SET password = %s WHERE username = %s',
                (hash_password(admin_password), admin_username)
            )
            cursor.execute(
                'UPDATE user_stats SET level = 999, exp = 999999, fish = 999999 WHERE username = %s',
                (admin_username,)
            )
            conn.commit()
            print("✅ 管理员账号已更新")
        
        cursor.execute('SELECT username FROM users WHERE username = %s AND is_admin = 1', ('admin',))
        if cursor.fetchone():
            cursor.execute('DELETE FROM users WHERE username = %s', ('admin',))
            cursor.execute('DELETE FROM user_stats WHERE username = %s', ('admin',))
            conn.commit()
            print("✅ 已删除旧版admin账号")
    except Exception as e:
        print(f"创建管理员账号时出错: {e}")
    
    cursor.close()
    conn.close()
    print("✅ 数据库表初始化完成")

# ====================
# 工具函数
# ====================
def hash_password(password):
    """密码加密"""
    return hashlib.sha256(password.encode()).hexdigest()

# ====================
# 用户相关接口
# ====================

@app.route('/api/user/register', methods=['POST'])
@app.route('/api/register', methods=['POST'])
def register():
    """用户注册"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空'})
    
    if len(username) < 2 or len(password) < 6:
        return jsonify({'success': False, 'message': '用户名至少2位，密码至少6位'})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT username FROM users WHERE username = %s', (username,))
        if cursor.fetchone():
            return jsonify({'success': False, 'message': '用户名已存在'})
        
        # 插入用户表
        cursor.execute(
            'INSERT INTO users (username, password) VALUES (%s, %s)',
            (username, hash_password(password))
        )
        
        # 插入用户属性表（默认值）
        cursor.execute(
            'INSERT INTO user_stats (username) VALUES (%s)',
            (username,)
        )
        
        conn.commit()
        return jsonify({'success': True, 'message': '注册成功'})
    
    except Exception as e:
        print(f"注册错误: {e}")
        return jsonify({'success': False, 'message': '注册失败'})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/user/login', methods=['POST'])
@app.route('/api/login', methods=['POST'])
def login():
    """用户登录"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        # 验证账号密码
        cursor.execute(
            'SELECT username, is_admin FROM users WHERE username = %s AND password = %s',
            (username, hash_password(password))
        )
        user = cursor.fetchone()
        
        if user:
            # 更新登录时间
            cursor.execute(
                'UPDATE users SET last_login = NOW() WHERE username = %s',
                (username,)
            )
            
            # 获取用户属性
            cursor.execute(
                'SELECT level, exp, fish FROM user_stats WHERE username = %s',
                (username,)
            )
            stats = cursor.fetchone()
            
            conn.commit()
            return jsonify({
                'success': True,
                'user': {
                    'username': user['username'],
                    'is_admin': user['is_admin'] == 1,
                    'level': stats['level'] if stats else 0,
                    'exp': stats['exp'] if stats else 0,
                    'fish': stats['fish'] if stats else 10
                }
            })
        else:
            return jsonify({'success': False, 'message': '用户名或密码错误'})
    
    except Exception as e:
        print(f"登录错误: {e}")
        return jsonify({'success': False, 'message': '登录失败'})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/user/<username>', methods=['GET', 'POST'])
def user_data(username):
    """获取或更新用户数据"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        if request.method == 'GET':
            # 获取用户数据（从user_stats表）
            cursor.execute('SELECT level, exp, fish FROM user_stats WHERE username = %s', (username,))
            user = cursor.fetchone()
            if user:
                return jsonify({
                    'success': True,
                    'level': user['level'],
                    'exp': user['exp'],
                    'fish': user['fish']
                })
            else:
                return jsonify({'success': False, 'message': '用户不存在'})
        
        elif request.method == 'POST':
            # 更新用户数据（更新user_stats表）
            data = request.get_json()
            level = data.get('level', 0)
            exp = data.get('exp', 0)
            fish = data.get('fish', 0)
            
            cursor.execute(
                'UPDATE user_stats SET level = %s, exp = %s, fish = %s WHERE username = %s',
                (level, exp, fish, username)
            )
            conn.commit()
            return jsonify({'success': True})
    
    except Exception as e:
        print(f"用户数据错误: {e}")
        return jsonify({'success': False, 'message': '操作失败'})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/user/<username>/sign', methods=['POST'])
def daily_sign(username):
    """每日签到"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        # 获取当前日期
        today = datetime.date.today().strftime('%Y-%m-%d')
        
        # 检查今日是否已签到（从user_stats表）
        cursor.execute(
            "SELECT last_sign, exp, fish FROM user_stats WHERE username = %s",
            (username,)
        )
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'success': False, 'message': '用户不存在'})
        
        if user['last_sign']:
            last_sign_date = user['last_sign'].strftime('%Y-%m-%d')
            if last_sign_date == today:
                return jsonify({'success': False, 'message': '今日已签到'})
        
        # 更新用户数据：+10经验 +3小鱼干，签到天数+1（更新user_stats表）
        cursor.execute(
            'UPDATE user_stats SET exp = exp + 10, fish = fish + 3, sign_days = sign_days + 1, last_sign = NOW() WHERE username = %s',
            (username,)
        )
        conn.commit()
        
        # 获取更新后的数据（从user_stats表）
        cursor.execute('SELECT level, exp, fish, sign_days FROM user_stats WHERE username = %s', (username,))
        user = cursor.fetchone()
        
        return jsonify({
            'success': True,
            'message': '签到成功！+10经验 +3小鱼干',
            'level': user['level'],
            'exp': user['exp'],
            'fish': user['fish'],
            'sign_days': user['sign_days']
        })
    
    except Exception as e:
        print(f"签到错误: {e}")
        return jsonify({'success': False, 'message': '签到失败'})
    finally:
        cursor.close()
        conn.close()

# ====================
# 留言相关接口
# ====================

@app.route('/api/message', methods=['POST'])
def add_message():
    """提交留言"""
    data = request.get_json()
    username = data.get('username')
    message = data.get('message')
    
    if not username or not message:
        return jsonify({'success': False, 'message': '用户名和留言不能为空'})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            'INSERT INTO messages (username, message) VALUES (%s, %s)',
            (username, message)
        )
        conn.commit()
        
        # 获取新插入的留言ID
        cursor.execute('SELECT LAST_INSERT_ID()')
        new_id = cursor.fetchone()[0]
        
        return jsonify({
            'success': True, 
            'message': '留言成功',
            'id': new_id
        })
    
    except Exception as e:
        print(f"留言错误: {e}")
        return jsonify({'success': False, 'message': '留言失败'})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/messages', methods=['GET'])
def get_messages():
    """获取所有留言（包含评论）"""
    # 从请求参数获取当前用户
    current_user = request.args.get('username', '')
    
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        cursor.execute('SELECT * FROM messages ORDER BY created_at DESC')
        messages = cursor.fetchall()
        
        # 检查message_likes表是否存在
        cursor.execute("SHOW TABLES LIKE 'message_likes'")
        likes_table_exists = cursor.fetchone() is not None
        
        # 为每条留言获取评论和点赞状态
        for msg in messages:
            cursor.execute('SELECT * FROM comments WHERE message_id = %s ORDER BY created_at DESC', (msg['id'],))
            comments = cursor.fetchall()
            
            # 为每条评论检查点赞状态
            comments_list = []
            for c in comments:
                liked_by_user = False
                if current_user:
                    cursor.execute("SHOW TABLES LIKE 'comment_likes'")
                    if cursor.fetchone():
                        cursor.execute('SELECT id FROM comment_likes WHERE comment_id = %s AND username = %s', (c['id'], current_user))
                        liked_by_user = cursor.fetchone() is not None
                
                comments_list.append({
                    'id': c['id'],
                    'message_id': c['message_id'],
                    'parent_id': c['parent_id'],
                    'username': c['username'],
                    'comment': c['comment'],
                    'likes': c['likes'] or 0,
                    'created_at': c['created_at'],
                    'liked_by_user': liked_by_user,
                    'reply_to_username': c.get('reply_to_username')
                })
            
            msg['comments'] = comments_list
            
            # 检查当前用户是否已点赞该留言
            msg['liked_by_user'] = False
            if current_user and likes_table_exists:
                cursor.execute('SELECT id FROM message_likes WHERE message_id = %s AND username = %s', (msg['id'], current_user))
                msg['liked_by_user'] = cursor.fetchone() is not None
        
        return jsonify({
            'success': True,
            'messages': messages
        })
    except Exception as e:
        print(f"获取留言错误: {e}")
        return jsonify({'success': False, 'message': '获取失败'})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/message/<int:message_id>/like', methods=['POST'])
def like_message(message_id):
    """点赞/取消点赞留言"""
    data = request.get_json()
    username = data.get('username')
    
    if not username:
        return jsonify({'success': False, 'message': '请先登录'})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 检查message_likes表是否存在
        cursor.execute("SHOW TABLES LIKE 'message_likes'")
        if not cursor.fetchone():
            # 表不存在，创建它
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS message_likes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    message_id INT NOT NULL,
                    username VARCHAR(50) NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY idx_message_user (message_id, username),
                    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            ''')
            conn.commit()
        
        # 检查用户是否已点赞
        cursor.execute('SELECT id FROM message_likes WHERE message_id = %s AND username = %s', (message_id, username))
        existing_like = cursor.fetchone()
        
        if existing_like:
            # 已点赞，取消点赞
            cursor.execute('DELETE FROM message_likes WHERE message_id = %s AND username = %s', (message_id, username))
            cursor.execute('UPDATE messages SET likes = likes - 1 WHERE id = %s', (message_id,))
            conn.commit()
            
            cursor.execute('SELECT likes FROM messages WHERE id = %s', (message_id,))
            result = cursor.fetchone()
            
            return jsonify({
                'success': True,
                'likes': result[0] if result else 0,
                'liked': False
            })
        else:
            # 未点赞，添加点赞
            cursor.execute('INSERT INTO message_likes (message_id, username) VALUES (%s, %s)', (message_id, username))
            cursor.execute('UPDATE messages SET likes = likes + 1 WHERE id = %s', (message_id,))
            conn.commit()
            
            cursor.execute('SELECT likes FROM messages WHERE id = %s', (message_id,))
            result = cursor.fetchone()
            
            return jsonify({
                'success': True,
                'likes': result[0] if result else 0,
                'liked': True
            })
    except Exception as e:
        print(f"点赞错误: {e}")
        return jsonify({'success': False, 'message': '点赞失败'})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/notifications/<username>', methods=['GET'])
def get_notifications(username):
    """获取用户的通知"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        cursor.execute('SELECT * FROM notifications WHERE target_user = %s ORDER BY created_at DESC', (username,))
        notifications = cursor.fetchall()
        
        return jsonify({'success': True, 'notifications': notifications})
    except Exception as e:
        print(f"获取通知错误: {e}")
        return jsonify({'success': False, 'message': '获取通知失败'})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
def mark_notification_read(notification_id):
    """标记通知为已读"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('UPDATE notifications SET is_read = TRUE WHERE id = %s', (notification_id,))
        conn.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"标记通知已读错误: {e}")
        return jsonify({'success': False, 'message': '标记失败'})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/notifications/<username>/read-all', methods=['POST'])
def mark_all_notifications_read(username):
    """标记所有通知为已读"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('UPDATE notifications SET is_read = TRUE WHERE target_user = %s', (username,))
        conn.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"标记所有通知已读错误: {e}")
        return jsonify({'success': False, 'message': '标记失败'})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/comment/<int:comment_id>/like', methods=['POST'])
def like_comment(comment_id):
    """评论点赞/取消点赞"""
    data = request.get_json()
    username = data.get('username')
    
    if not username:
        return jsonify({'success': False, 'message': '请先登录'})
    
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        # 检查comment_likes表是否存在
        cursor.execute("SHOW TABLES LIKE 'comment_likes'")
        if not cursor.fetchone():
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS comment_likes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    comment_id INT NOT NULL,
                    username VARCHAR(50) NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY idx_comment_user (comment_id, username),
                    FOREIGN KEY (comment_id) REFERENCES comments(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            ''')
            conn.commit()
        
        # 检查用户是否已点赞
        cursor.execute('SELECT id FROM comment_likes WHERE comment_id = %s AND username = %s', (comment_id, username))
        existing_like = cursor.fetchone()
        
        if existing_like:
            # 已点赞，取消点赞
            cursor.execute('DELETE FROM comment_likes WHERE comment_id = %s AND username = %s', (comment_id, username))
            cursor.execute('UPDATE comments SET likes = likes - 1 WHERE id = %s', (comment_id,))
            conn.commit()
            
            cursor.execute('SELECT likes FROM comments WHERE id = %s', (comment_id,))
            result = cursor.fetchone()
            
            return jsonify({
                'success': True,
                'likes': result['likes'] if result else 0,
                'liked': False
            })
        else:
            # 未点赞，添加点赞
            cursor.execute('INSERT INTO comment_likes (comment_id, username) VALUES (%s, %s)', (comment_id, username))
            cursor.execute('UPDATE comments SET likes = likes + 1 WHERE id = %s', (comment_id,))
            conn.commit()
            
            cursor.execute('SELECT likes FROM comments WHERE id = %s', (comment_id,))
            result = cursor.fetchone()
            
            return jsonify({
                'success': True,
                'likes': result['likes'] if result else 0,
                'liked': True
            })
    except Exception as e:
        print(f"评论点赞错误: {e}")
        return jsonify({'success': False, 'message': '点赞失败'})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/message/<int:message_id>/comment', methods=['POST'])
def add_comment(message_id):
    """添加评论（支持回复）"""
    data = request.get_json()
    username = data.get('username')
    comment_text = data.get('comment')
    parent_id = data.get('parent_id')  # 新增：父评论ID，用于回复
    reply_to_username = data.get('reply_to_username')  # 新增：被回复用户的用户名
    
    if not username or not comment_text:
        return jsonify({'success': False, 'message': '用户名和评论不能为空'})
    
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        # 处理parent_id，确保为None而不是undefined或空字符串
        if parent_id is None or parent_id == '' or parent_id == 'null':
            parent_id = None
        
        # 处理reply_to_username，确保为None而不是空字符串
        if reply_to_username is None or reply_to_username == '' or reply_to_username == 'null':
            reply_to_username = None
        
        cursor.execute(
            'INSERT INTO comments (message_id, parent_id, username, reply_to_username, comment) VALUES (%s, %s, %s, %s, %s)',
            (message_id, parent_id, username, reply_to_username, comment_text)
        )
        conn.commit()
        
        # 获取刚插入的评论ID
        cursor.execute('SELECT LAST_INSERT_ID()')
        new_comment_id = cursor.fetchone()[0]
        
        # 获取留言作者（用于发送通知）
        cursor.execute('SELECT username FROM messages WHERE id = %s', (message_id,))
        message_author = cursor.fetchone()
        
        # 如果有父评论，获取父评论的作者
        target_user = None
        notification_content = ""
        
        if parent_id:
            # 回复评论：通知父评论的作者
            cursor.execute('SELECT username FROM comments WHERE id = %s', (parent_id,))
            parent_comment = cursor.fetchone()
            if parent_comment and parent_comment['username'] != username:
                target_user = parent_comment['username']
                notification_content = f"💬 {username} 回复了你的评论：{comment_text[:20]}..."
        elif message_author and message_author['username'] != username:
            # 直接评论留言：通知留言作者
            target_user = message_author['username']
            notification_content = f"💬 {username} 评论了你的留言：{comment_text[:20]}..."
        
        # 如果需要发送通知
        if target_user and notification_content:
            cursor.execute(
                'INSERT INTO notifications (target_user, type, source_user, message_id, comment_id, content) VALUES (%s, %s, %s, %s, %s, %s)',
                (target_user, 'comment', username, message_id, new_comment_id, notification_content)
            )
            conn.commit()
        
        # 获取这条留言的所有评论，确保字段完整
        cursor.execute('''
            SELECT c.id, c.message_id, c.parent_id, c.username, c.reply_to_username, c.comment, c.likes, c.created_at
            FROM comments c 
            WHERE c.message_id = %s 
            ORDER BY c.created_at DESC
        ''', (message_id,))
        comments = cursor.fetchall()
        
        # 转换为普通字典，确保字段名正确
        comments_list = []
        for c in comments:
            # 检查当前用户是否已点赞该评论
            liked_by_user = False
            cursor.execute("SHOW TABLES LIKE 'comment_likes'")
            if cursor.fetchone():
                cursor.execute('SELECT id FROM comment_likes WHERE comment_id = %s AND username = %s', (c['id'], username))
                liked_by_user = cursor.fetchone() is not None
            
            comments_list.append({
                'id': c['id'],
                'message_id': c['message_id'],
                'parent_id': c['parent_id'],
                'username': c['username'],
                'comment': c['comment'],
                'likes': c['likes'] or 0,
                'created_at': c['created_at'].strftime('%Y-%m-%d %H:%M:%S') if c['created_at'] else None,
                'liked_by_user': liked_by_user,
                'reply_to_username': c['reply_to_username']  # 使用数据库中存储的值，不再重新查询
            })
        
        # 获取新创建的评论详情
        cursor.execute('SELECT id, message_id, parent_id, username, reply_to_username, comment, likes, created_at FROM comments WHERE id = %s', (new_comment_id,))
        new_comment = cursor.fetchone()
        
        new_comment_data = {
            'id': new_comment['id'],
            'message_id': new_comment['message_id'],
            'parent_id': new_comment['parent_id'],
            'username': new_comment['username'],
            'comment': new_comment['comment'],
            'likes': new_comment['likes'] or 0,
            'created_at': new_comment['created_at'].strftime('%Y-%m-%d %H:%M:%S') if new_comment['created_at'] else None,
            'liked_by_user': False,
            'reply_to_username': new_comment.get('reply_to_username')
        } if new_comment else None
        
        return jsonify({
            'success': True, 
            'message': '评论成功',
            'comments': comments_list,
            'comment': new_comment_data
        })
    except Exception as e:
        print(f"评论错误: {e}")
        return jsonify({'success': False, 'message': '评论失败'})
    finally:
        cursor.close()
        conn.close()

# ====================
# 排行榜接口
# ====================

@app.route('/api/leaderboard', methods=['GET'])
def get_leaderboard():
    """获取用户排行榜（按小鱼干数量）"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        cursor.execute('''
            SELECT u.username, us.level, us.fish, us.exp
            FROM users u
            LEFT JOIN user_stats us ON u.username = us.username
            WHERE u.is_admin = 0
            ORDER BY us.fish DESC, us.level DESC
            LIMIT 20
        ''')
        users = cursor.fetchall()
        
        # 确保所有字段有默认值
        for user in users:
            user['level'] = user.get('level') or 0
            user['fish'] = user.get('fish') or 0
            user['exp'] = user.get('exp') or 0
        
        return jsonify({'success': True, 'data': users})
    except Exception as e:
        print(f"获取排行榜错误: {e}")
        return jsonify({'success': False, 'message': '获取排行榜失败'})
    finally:
        cursor.close()
        conn.close()

# ====================
# 游戏成绩接口
# ====================

@app.route('/api/game/score', methods=['POST'])
def save_game_score():
    """保存游戏成绩"""
    data = request.get_json()
    username = data.get('username')
    game_name = data.get('game_name')
    score = data.get('score', 0)
    score_type = data.get('score_type', 'score')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 检查是否有更好的成绩
        cursor.execute(
            'SELECT score FROM game_scores WHERE username = %s AND game_name = %s',
            (username, game_name)
        )
        existing = cursor.fetchone()
        
        # 判断是否为"越小越好"的成绩类型（翻牌数、步数）
        is_lower_better = score_type in ['翻牌数', '步数']
        
        if existing:
            if is_lower_better:
                # 翻牌数和步数是越小越好
                if existing[0] <= score:
                    return jsonify({'success': False, 'message': '未打破记录'})
            else:
                # 其他成绩是越高越好
                if existing[0] >= score:
                    return jsonify({'success': False, 'message': '未打破记录'})
        
        # 更新或插入成绩
        cursor.execute(
            'REPLACE INTO game_scores (username, game_name, score, score_type) VALUES (%s, %s, %s, %s)',
            (username, game_name, score, score_type)
        )
        conn.commit()
        return jsonify({'success': True, 'message': '成绩已保存'})
    
    except Exception as e:
        print(f"保存成绩错误: {e}")
        return jsonify({'success': False, 'message': '保存失败'})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/game/score/<username>/<game_name>', methods=['GET'])
def get_game_score(username, game_name):
    """获取用户游戏成绩"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        cursor.execute(
            'SELECT score, score_type FROM game_scores WHERE username = %s AND game_name = %s',
            (username, game_name)
        )
        result = cursor.fetchone()
        if result:
            return jsonify({
                'success': True,
                'score': result['score'],
                'score_type': result['score_type']
            })
        else:
            return jsonify({'success': False, 'message': '暂无成绩'})
    except Exception as e:
        print(f"获取成绩错误: {e}")
        return jsonify({'success': False, 'message': '获取失败'})
    finally:
        cursor.close()
        conn.close()

# ====================
# 成就接口
# ====================

@app.route('/api/achievement/<username>', methods=['GET', 'POST'])
def achievement(username):
    """获取或解锁成就"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        if request.method == 'GET':
            # 获取用户所有成就
            cursor.execute(
                'SELECT achievement_id, unlocked, unlocked_at FROM achievements WHERE username = %s',
                (username,)
            )
            achievements = cursor.fetchall()
            return jsonify({'success': True, 'achievements': achievements})
        
        elif request.method == 'POST':
            # 解锁成就
            data = request.get_json()
            achievement_id = data.get('achievement_id')
            
            cursor.execute(
                'SELECT unlocked FROM achievements WHERE username = %s AND achievement_id = %s',
                (username, achievement_id)
            )
            existing = cursor.fetchone()
            
            if existing and existing['unlocked']:
                return jsonify({'success': False, 'message': '成就已解锁'})
            
            cursor.execute(
                'REPLACE INTO achievements (username, achievement_id, unlocked, unlocked_at) VALUES (%s, %s, TRUE, NOW())',
                (username, achievement_id)
            )
            conn.commit()
            return jsonify({'success': True, 'message': '成就解锁成功'})
    
    except Exception as e:
        print(f"成就操作错误: {e}")
        return jsonify({'success': False, 'message': '操作失败'})
    finally:
        cursor.close()
        conn.close()



# ====================
# 管理员相关接口
# ====================

def is_admin_request():
    """检查请求是否来自管理员（验证用户名是否为管理员）"""
    admin_username = request.headers.get('X-Admin-User') or request.args.get('admin_user')
    if admin_username:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT is_admin FROM users WHERE username = %s', (admin_username,))
            result = cursor.fetchone()
            return result and result[0] == 1
        except:
            return False
        finally:
            cursor.close()
            conn.close()
    return True  # 暂时默认允许（前端已有管理员检查）

@app.route('/api/admin/stats', methods=['GET'])
def admin_stats():
    """获取后台统计数据"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        # 用户总数
        cursor.execute('SELECT COUNT(*) as count FROM users')
        user_count = cursor.fetchone()['count']
        
        # 留言总数
        cursor.execute('SELECT COUNT(*) as count FROM messages')
        message_count = cursor.fetchone()['count']
        
        # 今日新增
        today = datetime.date.today().strftime('%Y-%m-%d')
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE DATE(created_at) = %s", (today,))
        new_users_today = cursor.fetchone()['count']
        
        # 最近用户
        cursor.execute('SELECT username, created_at FROM users ORDER BY created_at DESC LIMIT 10')
        recent_users = cursor.fetchall()
        
        # 最近留言
        cursor.execute('SELECT id, username, message, created_at FROM messages ORDER BY created_at DESC LIMIT 10')
        recent_messages = cursor.fetchall()
        
        # 所有用户统计
        cursor.execute('''
            SELECT u.username, u.created_at, u.last_login, us.level, us.exp, us.fish 
            FROM users u LEFT JOIN user_stats us ON u.username = us.username 
            ORDER BY u.created_at DESC
        ''')
        all_users = cursor.fetchall()
        
        return jsonify({
            'success': True,
            'user_count': user_count,
            'message_count': message_count,
            'new_users_today': new_users_today,
            'recent_users': recent_users,
            'recent_messages': recent_messages,
            'all_users': all_users
        })
    except Exception as e:
        print(f"获取统计数据错误: {e}")
        return jsonify({'success': False, 'message': '获取失败'})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/admin/charts/new_users', methods=['GET'])
def admin_chart_new_users():
    """获取每日新增用户数据"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        cursor.execute('''
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM users
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            GROUP BY DATE(created_at)
            ORDER BY date ASC
        ''')
        data = cursor.fetchall()
        
        dates = []
        counts = []
        for item in data:
            dates.append(item['date'].strftime('%m-%d'))
            counts.append(item['count'])
        
        return jsonify({'success': True, 'dates': dates, 'counts': counts})
    except Exception as e:
        print(f"获取新增用户数据错误: {e}")
        return jsonify({'success': False, 'message': '获取失败'})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/admin/charts/active_users', methods=['GET'])
def admin_chart_active_users():
    """获取每日活跃用户数据"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        cursor.execute('''
            SELECT DATE(last_login) as date, COUNT(*) as count
            FROM users
            WHERE last_login >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            GROUP BY DATE(last_login)
            ORDER BY date ASC
        ''')
        data = cursor.fetchall()
        
        dates = []
        counts = []
        for item in data:
            dates.append(item['date'].strftime('%m-%d'))
            counts.append(item['count'])
        
        return jsonify({'success': True, 'dates': dates, 'counts': counts})
    except Exception as e:
        print(f"获取活跃用户数据错误: {e}")
        return jsonify({'success': False, 'message': '获取失败'})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/admin/charts/sign_users', methods=['GET'])
def admin_chart_sign_users():
    """获取每日签到用户数据"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        cursor.execute('''
            SELECT DATE(last_sign) as date, COUNT(*) as count, SUM(sign_days) as total_days
            FROM user_stats
            WHERE last_sign >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            GROUP BY DATE(last_sign)
            ORDER BY date ASC
        ''')
        data = cursor.fetchall()
        
        dates = []
        counts = []
        totals = []
        for item in data:
            dates.append(item['date'].strftime('%m-%d'))
            counts.append(item['count'])
            totals.append(item['total_days'])
        
        return jsonify({'success': True, 'dates': dates, 'counts': counts, 'totals': totals})
    except Exception as e:
        print(f"获取签到用户数据错误: {e}")
        return jsonify({'success': False, 'message': '获取失败'})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/admin/charts/level_dist', methods=['GET'])
def admin_chart_level_dist():
    """获取用户等级分布数据"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        cursor.execute('''
            SELECT level, COUNT(*) as count
            FROM user_stats
            WHERE level IS NOT NULL
            GROUP BY level
            ORDER BY level ASC
        ''')
        data = cursor.fetchall()
        
        levels = []
        counts = []
        for item in data:
            levels.append(f"Lv.{item['level']}")
            counts.append(item['count'])
        
        return jsonify({'success': True, 'levels': levels, 'counts': counts})
    except Exception as e:
        print(f"获取等级分布数据错误: {e}")
        return jsonify({'success': False, 'message': '获取失败'})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/admin/users', methods=['GET'])
def admin_get_users():
    """获取所有用户列表"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        cursor.execute('''
            SELECT u.id, u.username, u.is_admin, u.created_at, u.last_login, 
                   us.level, us.exp, us.fish, us.sign_days, us.last_sign
            FROM users u LEFT JOIN user_stats us ON u.username = us.username
            ORDER BY u.created_at DESC
        ''')
        users = cursor.fetchall()
        return jsonify({'success': True, 'users': users})
    except Exception as e:
        print(f"获取用户列表错误: {e}")
        return jsonify({'success': False, 'message': '获取失败'})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/admin/user/<username>', methods=['DELETE'])
def admin_delete_user(username):
    """删除用户（管理员）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('DELETE FROM users WHERE username = %s', (username,))
        conn.commit()
        return jsonify({'success': True, 'message': '用户已删除'})
    except Exception as e:
        print(f"删除用户错误: {e}")
        return jsonify({'success': False, 'message': '删除失败'})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/admin/user/<username>', methods=['PUT'])
def admin_update_user(username):
    """更新用户信息（管理员）"""
    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 更新用户统计数据
        cursor.execute('''
            UPDATE user_stats 
            SET level = %s, exp = %s, fish = %s 
            WHERE username = %s
        ''', (
            data.get('level', 0),
            data.get('exp', 0),
            data.get('fish', 10),
            username
        ))
        conn.commit()
        return jsonify({'success': True, 'message': '用户信息已更新'})
    except Exception as e:
        print(f"更新用户信息错误: {e}")
        return jsonify({'success': False, 'message': '更新失败'})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/admin/message/<message_id>', methods=['DELETE'])
def admin_delete_message(message_id):
    """删除留言（管理员）- 级联删除相关评论"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 先删除该留言的所有评论
        cursor.execute('DELETE FROM comments WHERE message_id = %s', (message_id,))
        # 再删除留言本身
        cursor.execute('DELETE FROM messages WHERE id = %s', (message_id,))
        conn.commit()
        return jsonify({'success': True, 'message': '留言及相关评论已删除'})
    except Exception as e:
        print(f"删除留言错误: {e}")
        return jsonify({'success': False, 'message': '删除失败'})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/admin/game-scores', methods=['GET'])
def admin_get_game_scores():
    """获取所有用户的游戏成绩（管理员）"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        # 获取所有游戏成绩，按用户名和游戏名排序
        cursor.execute('''
            SELECT gs.username, gs.game_name, gs.score, gs.score_type, gs.created_at,
                   us.level, us.fish
            FROM game_scores gs
            LEFT JOIN user_stats us ON gs.username = us.username
            ORDER BY gs.username, gs.game_name
        ''')
        scores = cursor.fetchall()
        
        # 获取游戏统计信息
        cursor.execute('''
            SELECT game_name, COUNT(*) as player_count, 
                   MAX(score) as max_score, 
                   MIN(score) as min_score
            FROM game_scores
            GROUP BY game_name
        ''')
        game_stats = cursor.fetchall()
        
        return jsonify({
            'success': True,
            'scores': scores,
            'game_stats': game_stats
        })
    except Exception as e:
        print(f"获取游戏成绩错误: {e}")
        return jsonify({'success': False, 'message': '获取失败'})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/admin/achievements', methods=['GET'])
def admin_get_achievements():
    """获取所有成就记录（管理员）"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        cursor.execute('''
            SELECT a.username, a.achievement_id, a.unlocked, a.unlocked_at,
                   us.level, us.fish
            FROM achievements a
            LEFT JOIN user_stats us ON a.username = us.username
            ORDER BY a.username, a.achievement_id
        ''')
        achievements = cursor.fetchall()
        
        # 统计每个用户解锁的成就数量
        cursor.execute('''
            SELECT username, COUNT(*) as total, SUM(CASE WHEN unlocked THEN 1 ELSE 0 END) as unlocked_count
            FROM achievements
            GROUP BY username
        ''')
        user_stats = cursor.fetchall()
        
        return jsonify({
            'success': True,
            'achievements': achievements,
            'user_stats': user_stats
        })
    except Exception as e:
        print(f"获取成就记录错误: {e}")
        return jsonify({'success': False, 'message': '获取失败'})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/admin/comments', methods=['GET'])
def admin_get_comments():
    """获取所有评论记录（管理员）- 支持多级评论"""
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        # 获取所有评论及其所属留言信息
        cursor.execute('''
            SELECT c.id, c.message_id, c.parent_id, c.username, c.comment, c.likes, c.created_at,
                   m.message as parent_message, m.username as message_author
            FROM comments c
            LEFT JOIN messages m ON c.message_id = m.id
            ORDER BY c.message_id, c.created_at
        ''')
        comments = cursor.fetchall()
        
        # 格式化时间
        for c in comments:
            if c['created_at']:
                c['created_at'] = c['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        # 统计留言的评论数
        cursor.execute('''
            SELECT message_id, COUNT(*) as comment_count
            FROM comments
            GROUP BY message_id
        ''')
        comment_counts = cursor.fetchall()
        
        return jsonify({
            'success': True,
            'comments': comments,
            'comment_counts': comment_counts
        })
    except Exception as e:
        print(f"获取评论记录错误: {e}")
        return jsonify({'success': False, 'message': '获取失败'})
    finally:
        cursor.close()
        conn.close()

@app.route('/api/admin/comment/<int:comment_id>', methods=['DELETE'])
def admin_delete_comment(comment_id):
    """删除评论（管理员）- 同时删除关联的点赞记录"""
    # 验证管理员权限
    if 'admin_user' not in session:
        return jsonify({'success': False, 'message': '未授权'})
    
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    try:
        # 先删除关联的点赞记录
        cursor.execute('DELETE FROM comment_likes WHERE comment_id = %s', (comment_id,))
        
        # 删除评论
        cursor.execute('DELETE FROM comments WHERE id = %s', (comment_id,))
        conn.commit()
        
        return jsonify({'success': True, 'message': '删除成功'})
    except Exception as e:
        print(f"删除评论错误: {e}")
        conn.rollback()
        return jsonify({'success': False, 'message': '删除失败'})
    finally:
        cursor.close()
        conn.close()

# ====================
# 健康检查
# ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({'status': 'ok', 'message': '哈基米后端服务运行正常'})

# ====================
# 静态文件服务
# ====================

@app.route('/')
def index():
    """首页"""
    return send_from_directory('.', 'index-main.html')

@app.route('/<path:filename>')
def static_files(filename):
    """静态文件访问"""
    return send_from_directory('.', filename)

# ====================
# 主函数
# ====================

if __name__ == '__main__':
    # 初始化数据库
    init_database()
    
    # 启动服务
    app.run(
        host='0.0.0.0',
        port=8080,
        debug=False
    )

# ====================
# API接口列表
# ====================
#
# 用户相关:
# POST   /api/user/register    - 用户注册 {username, password}
# POST   /api/user/login       - 用户登录 {username, password}
# GET    /api/user/{username}  - 获取用户数据
# POST   /api/user/{username}  - 更新用户数据 {level, exp, fish}
# POST   /api/user/{username}/sign - 每日签到
#
# 留言相关:
# POST   /api/message          - 提交留言 {username, message}
# GET    /api/messages         - 获取所有留言
#
# 游戏成绩:
# POST   /api/game/score       - 保存游戏成绩 {username, game_name, score, score_type}
# GET    /api/game/score/{username}/{game_name} - 获取用户游戏成绩
#
# 成就相关:
# GET    /api/achievement/{username} - 获取用户成就
# POST   /api/achievement/{username} - 解锁成就 {achievement_id}
#
# 健康检查:
# GET    /api/health           - 健康检查
# ====================