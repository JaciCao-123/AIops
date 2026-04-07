# SSL 证书管理技能

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 诊断流程](#2-诊断流程)
- [3. 诊断命令集](#3-诊断命令集)
- [4. 证书管理](#4-证书管理)
- [5. 常见问题与解决方案](#5-常见问题与解决方案)
- [6. 权限边界](#6-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `SSL`, `证书`, `certificate`, `HTTPS`
- `过期`, `expire`, `renew`, `续签`
- `Let's Encrypt`, `certbot`, `acme`
- `TLS`, `域名`, `公钥`, `私钥`

### 1.2 适用条件
- SSL 证书过期检查
- 证书续签
- 证书配置问题
- HTTPS 连接问题
- 证书链验证

---

## 2. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 检查证书状态                                       │
│  - 查看证书有效期                                          │
│  - 检查证书链                                              │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 验证证书配置                                       │
│  - 检查 Web 服务器配置                                     │
│  - 验证 HTTPS 连接                                         │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 证书续签（如需要）                                 │
│  - 自动续签                                                │
│  - 手动续签                                                │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 验证续签结果                                       │
│  - 重启服务                                                │
│  - 验证新证书                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 诊断命令集

### 3.1 证书信息查看

#### 查看本地证书文件
```bash
# 查看证书详细信息
openssl x509 -in /etc/ssl/certs/cert.pem -text -noout

# 查看证书有效期
openssl x509 -in /etc/ssl/certs/cert.pem -dates -noout

# 查看证书主题
openssl x509 -in /etc/ssl/certs/cert.pem -subject -noout

# 查看证书颁发者
openssl x509 -in /etc/ssl/certs/cert.pem -issuer -noout

# 查看 SAN (Subject Alternative Names)
openssl x509 -in /etc/ssl/certs/cert.pem -ext subjectAltName -noout

# 查看证书指纹
openssl x509 -in /etc/ssl/certs/cert.pem -fingerprint -noout

# 验证私钥和证书是否匹配
openssl x509 -noout -modulus -in cert.pem | openssl md5
openssl rsa -noout -modulus -in key.pem | openssl md5
```

#### 查看远程服务器证书
```bash
# 查看远程证书信息
openssl s_client -connect example.com:443 -servername example.com 2>/dev/null | openssl x509 -noout -dates

# 查看完整证书链
openssl s_client -connect example.com:443 -servername example.com -showcerts

# 检查证书过期时间
echo | openssl s_client -connect example.com:443 -servername example.com 2>/dev/null | openssl x509 -noout -enddate

# 检查特定端口
openssl s_client -connect example.com:636 -servername example.com 2>/dev/null | openssl x509 -noout -dates
```

#### 使用 certbot 查看
```bash
# 查看已安装的证书
certbot certificates

# 查看特定证书
certbot certificates --cert-name example.com
```

### 3.2 证书过期检查

```bash
# 检查本地证书过期时间
openssl x509 -in /etc/ssl/certs/cert.pem -noout -checkend 0
echo $?  # 0 表示未过期, 1 表示已过期

# 检查是否在 30 天内过期
openssl x509 -in /etc/ssl/certs/cert.pem -noout -checkend 2592000

# 批量检查证书过期
for cert in /etc/ssl/certs/*.pem; do
  echo "=== $cert ==="
  openssl x509 -in "$cert" -noout -dates
done

# 检查远程证书过期天数
echo | openssl s_client -connect example.com:443 2>/dev/null | openssl x509 -noout -enddate | cut -d= -f2 | xargs -I {} date -d {} +%s | xargs -I {} echo $(( ({} - $(date +%s)) / 86400 )) days remaining
```

### 3.3 证书链验证

```bash
# 验证证书链
openssl verify -CAfile /etc/ssl/certs/ca-bundle.crt /etc/ssl/certs/cert.pem

# 验证完整证书链
cat cert.pem intermediate.pem > fullchain.pem
openssl verify -CAfile root.pem -untrusted intermediate.pem cert.pem

# 在线验证证书链
# https://www.ssllabs.com/ssltest/
```

---

## 4. 证书管理

### 4.1 Let's Encrypt 证书申请

```bash
# 安装 certbot
# Ubuntu/Debian
apt-get install certbot python3-certbot-nginx
# CentOS/RHEL
yum install certbot python3-certbot-nginx

# 申请证书 (Nginx)
certbot --nginx -d example.com -d www.example.com

# 申请证书 (Apache)
certbot --apache -d example.com -d www.example.com

# 仅申请证书（手动配置）
certbot certonly --standalone -d example.com

# 使用 DNS 验证
certbot certonly --manual --preferred-challenges dns -d example.com

# 通配符证书
certbot certonly --manual --preferred-challenges dns -d "*.example.com" -d example.com
```

### 4.2 证书续签

```bash
# 测试续签（不实际执行）
certbot renew --dry-run

# 手动续签所有证书
certbot renew

# 续签特定证书
certbot renew --cert-name example.com

# 强制续签
certbot renew --force-renewal

# 设置自动续签（cron）
# crontab -e
0 0 * * * certbot renew --quiet --post-hook "systemctl reload nginx"
```

### 4.3 证书安装

#### Nginx 配置
```nginx
server {
    listen 443 ssl http2;
    server_name example.com;

    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_session_tickets off;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    # HSTS
    add_header Strict-Transport-Security "max-age=63072000" always;
}

server {
    listen 80;
    server_name example.com;
    return 301 https://$server_name$request_uri;
}
```

#### Apache 配置
```apache
<VirtualHost *:443>
    ServerName example.com
    
    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/example.com/cert.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/example.com/privkey.pem
    SSLCertificateChainFile /etc/letsencrypt/live/example.com/chain.pem
    
    SSLProtocol all -SSLv2 -SSLv3
    SSLCipherSuite HIGH:!aNULL:!MD5
</VirtualHost>
```

### 4.4 自签名证书

```bash
# 生成私钥
openssl genrsa -out key.pem 2048

# 生成证书签名请求 (CSR)
openssl req -new -key key.pem -out csr.pem

# 生成自签名证书
openssl req -x509 -key key.pem -in csr.pem -out cert.pem -days 365

# 一键生成自签名证书
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"
```

---

## 5. 常见问题与解决方案

### 5.1 证书过期

**现象**: 浏览器显示证书过期警告

**诊断步骤**:
```bash
# 检查证书有效期
openssl x509 -in /etc/ssl/certs/cert.pem -noout -dates

# 检查远程证书
echo | openssl s_client -connect example.com:443 2>/dev/null | openssl x509 -noout -dates
```

**解决方案**:
```bash
# 续签 Let's Encrypt 证书
certbot renew

# 重启 Web 服务
systemctl reload nginx
systemctl reload apache2
```

### 5.2 证书链不完整

**现象**: 浏览器显示证书不受信任

**诊断步骤**:
```bash
# 验证证书链
openssl verify -CAfile /etc/ssl/certs/ca-bundle.crt cert.pem

# 检查证书链
openssl s_client -connect example.com:443 -showcerts
```

**解决方案**:
```bash
# 使用 fullchain.pem 而不是 cert.pem
# Nginx 配置
ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;

# 下载中间证书
wget -O intermediate.pem https://letsencrypt.org/certs/lets-encrypt-r3.pem
cat cert.pem intermediate.pem > fullchain.pem
```

### 5.3 域名不匹配

**现象**: 证书域名与访问域名不匹配

**诊断步骤**:
```bash
# 查看证书包含的域名
openssl x509 -in cert.pem -noout -text | grep -A1 "Subject Alternative Name"
```

**解决方案**:
```bash
# 申请新证书包含所有域名
certbot --nginx -d example.com -d www.example.com -d api.example.com

# 申请通配符证书
certbot certonly --manual --preferred-challenges dns -d "*.example.com" -d example.com
```

### 5.4 HTTPS 重定向问题

**现象**: HTTP 未自动跳转到 HTTPS

**解决方案**:
```nginx
# Nginx 配置
server {
    listen 80;
    server_name example.com;
    return 301 https://$server_name$request_uri;
}
```

### 5.5 混合内容警告

**现象**: HTTPS 页面加载 HTTP 资源

**解决方案**:
```html
<!-- 使用相对协议 -->
<script src="//cdn.example.com/script.js"></script>

<!-- 或使用 HTTPS -->
<script src="https://cdn.example.com/script.js"></script>
```

---

## 6. 权限边界

### 6.1 安全的只读操作
```bash
openssl x509 -text -noout
openssl s_client
certbot certificates
```

### 6.2 需要确认的操作
```bash
certbot renew
certbot certonly
systemctl reload nginx/apache2
```

### 6.3 危险操作禁止执行
```bash
rm -rf /etc/letsencrypt/
rm -rf /etc/ssl/
chmod 777 /etc/ssl/private/
```

---

## 7. 快速诊断脚本

```bash
#!/bin/bash
# SSL 证书快速诊断脚本

DOMAIN="$1"
PORT="${2:-443}"

if [ -z "$DOMAIN" ]; then
  echo "Usage: $0 <domain> [port]"
  exit 1
fi

echo "=== 证书信息 ==="
echo | openssl s_client -connect $DOMAIN:$PORT -servername $DOMAIN 2>/dev/null | openssl x509 -noout -subject -issuer -dates

echo -e "\n=== SAN 域名 ==="
echo | openssl s_client -connect $DOMAIN:$PORT -servername $DOMAIN 2>/dev/null | openssl x509 -noout -ext subjectAltName

echo -e "\n=== 过期检查 ==="
EXPIRE_DATE=$(echo | openssl s_client -connect $DOMAIN:$PORT -servername $DOMAIN 2>/dev/null | openssl x509 -noout -enddate | cut -d= -f2)
EXPIRE_EPOCH=$(date -d "$EXPIRE_DATE" +%s 2>/dev/null || date -j -f "%b %d %T %Y %Z" "$EXPIRE_DATE" +%s)
NOW_EPOCH=$(date +%s)
DAYS_LEFT=$(( (EXPIRE_EPOCH - NOW_EPOCH) / 86400 ))
echo "过期时间: $EXPIRE_DATE"
echo "剩余天数: $DAYS_LEFT 天"

if [ $DAYS_LEFT -lt 30 ]; then
  echo "⚠️  警告: 证书将在 30 天内过期!"
elif [ $DAYS_LEFT -lt 0 ]; then
  echo "❌ 错误: 证书已过期!"
else
  echo "✅ 证书状态正常"
fi

echo -e "\n=== SSL 配置检查 ==="
echo | openssl s_client -connect $DOMAIN:$PORT -servername $DOMAIN 2>/dev/null | grep -E "Protocol|Cipher"
```

---

## 8. 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-05
- 维护者: AIOps Team
