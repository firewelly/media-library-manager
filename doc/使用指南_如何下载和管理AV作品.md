# 使用指南：如何下载和管理AV作品

## 概述

本文档提供使用长泽梓作品列表数据进行下载和管理的完整指南，适用于任何使用 `javdb_actor_all.py` 程序获取的演员作品数据。

## 下载前准备

### 1. 环境要求
- **Python 3.7+** 环境
- **网络环境**：建议使用代理提高下载速度
- **存储空间**：确保有足够硬盘空间
- **下载工具**：推荐支持磁力链接的下载软件

### 2. 数据文件
确保已获取以下文件：
- `演员姓名_完整作品列表.csv` - 包含所有作品信息
- `演员姓名_all_works.csv` - 有码作品数据
- `演员姓名_无码作品.csv` - 无码作品数据

## 下载方法

### 方法一：使用磁力链接直接下载

1. **打开CSV文件**
   ```python
   import pandas as pd
   df = pd.read_csv('长泽梓_完整作品列表.csv')
   ```

2. **筛选要下载的作品**
   ```python
   # 按条件筛选
   high_rating = df[df['rating'] >= 4.5]  # 高评分作品
   recent_works = df[df['release_date'] >= '2020-01-01']  # 近期作品
   uncensored = df[df['title'].str.contains('无码|無碼', na=False)]  # 无码作品
   ```

3. **获取磁力链接**
   ```python
   # 获取磁力链接列表
   magnet_links = df['magnet_link'].dropna().tolist()
   
   # 保存为下载列表文件
   with open('下载列表.txt', 'w') as f:
       for link in magnet_links:
           f.write(f"{link}\\n")
   ```

### 方法二：使用下载软件批量下载

1. **qBittorrent**
   - 导入磁力链接列表文件
   - 设置下载目录和速度限制
   - 批量开始下载

2. **迅雷**
   - 支持磁力链接直接下载
   - 可设置同时下载任务数
   - 支持断点续传

3. **其他BT客户端**
   - μTorrent、BitComet等
   - 选择支持磁力链接的软件

## 文件管理

### 1. 文件命名规范
建议命名格式：`[发行日期] [番号] [标题]`

示例：
```
[2012-12-01] PPPD-123 巨乳女教师 长泽梓
[2011-06-22] 062211_120 无码 奇迹的爆乳娘 长泽梓
```

### 2. 文件夹组织
```
长泽梓作品集/
├── 有码作品/
│   ├── 2011年/
│   ├── 2012年/
│   └── ...
├── 无码作品/
│   ├── 一本道/
│   ├── 加勒比/
│   └── ...
├── 精选收藏/
├── 高分作品/
└── 待整理/
```

### 3. 数据管理
- **Excel管理**：使用Excel建立作品档案
- **数据库管理**：使用SQLite等轻量级数据库
- **媒体管理软件**：使用专门的AV媒体管理软件

## 质量筛选

### 1. 评分筛选
```python
# 筛选高评分作品（4.5分以上）
high_quality = df[df['rating'] >= 4.5]

# 筛选中等评分作品（4.0-4.5分）
medium_quality = df[(df['rating'] >= 4.0) & (df['rating'] < 4.5)]

# 按评分排序
top_rated = df.sort_values('rating', ascending=False)
```

### 2. 制作商筛选
```python
# 知名制作商列表
top_studios = ['MOODYZ', 'S1', 'Madonna', 'OPPAI', 'Fitch']

# 筛选优质制作商作品
premium_works = df[df['studio'].isin(top_studios)]
```

### 3. 时期筛选
```python
# 巅峰期作品（假设2012年为巅峰期）
peak_period = df[df['release_date'].str.startswith('2012')]

# 近期作品（2020年后）
recent_works = df[df['release_date'] >= '2020-01-01']
```

## 下载策略

### 1. 优先级策略
**第一优先级**：
- 评分4.5分以上的作品
- 知名制作商的作品
- 演员巅峰期作品

**第二优先级**：
- 评分4.0-4.5分的作品
- 特殊题材或经典作品
- 个人偏好类型

**第三优先级**：
- 评分3.5-4.0分的作品
- 补全收藏的作品
- 新发布的作品

### 2. 下载顺序
1. **先下载样本**：每种类型先下载1-2部确认质量
2. **批量下载**：确认质量后进行批量下载
3. **补全收藏**：逐步完善收藏
4. **定期更新**：关注新作品发布

## 存储优化

### 1. 空间管理
- **定期清理**：删除重复或质量较差的作品
- **压缩存储**：对不常观看的作品进行压缩
- **云存储**：重要作品可备份到云盘
- **外置硬盘**：大量收藏建议使用外置硬盘

### 2. 质量平衡
- **高清优先**：存储空间充足时优先下载高清版本
- **精选收藏**：保留最佳画质的版本
- **合理取舍**：在质量和存储空间间找到平衡

## 隐私保护

### 1. 文件隐藏
- **隐藏文件夹**：设置文件夹为隐藏属性
- **加密存储**：使用加密软件保护重要文件
- **分散存储**：不要将所有文件放在同一位置

### 2. 网络安全
- **使用VPN**：下载时使用VPN保护隐私
- **清理记录**：定期清理下载和浏览记录
- **安全软件**：使用可靠的安全软件防护

## 法律合规

### 1. 版权注意
- **个人使用**：仅限个人收藏和观看
- **禁止传播**：不要上传到网络或分享给他人
- **合法来源**：确保从合法渠道获取作品

### 2. 地区法律
- **了解法规**：了解所在地区的相关法律法规
- **年龄限制**：确保已达到法定年龄
- **内容限制**：注意某些类型作品的合法性

## 常见问题

### Q1：磁力链接无法下载怎么办？
**A**：
1. 检查网络连接
2. 尝试使用代理或VPN
3. 更换下载软件
4. 寻找其他资源来源

### Q2：下载速度很慢怎么办？
**A**：
1. 选择种子数多的链接
2. 使用高速网络
3. 调整下载软件设置
4. 避开网络高峰时段

### Q3：如何识别作品质量？
**A**：
1. 参考评分和用户评论
2. 查看制作商和演员阵容
3. 预览截图或预告片
4. 从小文件开始试下载

### Q4：存储空间不足怎么办？
**A**：
1. 优先下载高评分作品
2. 删除重复或低质量文件
3. 使用压缩技术
4. 购买更大容量存储设备

## 高级技巧

### 1. 自动化脚本
```python
# 自动下载脚本示例
def auto_download(df, min_rating=4.0, max_size_gb=100):
    filtered = df[df['rating'] >= min_rating]
    total_size = 0
    for _, work in filtered.iterrows():
        if total_size < max_size_gb:
            download_magnet(work['magnet_link'])
            total_size += estimate_size(work)
```

### 2. 数据可视化
```python
# 制作统计图表
import matplotlib.pyplot as plt

# 评分分布图
df['rating'].hist(bins=20)
plt.title('作品评分分布')
plt.show()

# 时间趋势图
df.groupby('year').size().plot()
plt.title('作品数量时间趋势')
plt.show()
```

### 3. 智能推荐
```python
# 基于历史偏好推荐
def recommend_works(df, liked_works, top_n=10):
    # 根据喜欢的作品特征推荐相似作品
    similar_studios = liked_works['studio'].value_counts().head(3).index
    similar_ratings = liked_works['rating'].mean()
    
    recommendations = df[
        (df['studio'].isin(similar_studios)) &
        (df['rating'] >= similar_ratings - 0.2)
    ].head(top_n)
    
    return recommendations
```

## 总结

通过合理使用 `javdb_actor_all.py` 获取的作品数据，配合本指南的下载和管理方法，可以高效地建立和管理个人AV收藏。记住要遵守法律法规，尊重版权，合理控制收藏规模，享受高质量的观影体验。

---

*指南更新时间：2024年*
*适用于：javdb_actor_all.py 获取的所有演员作品数据*