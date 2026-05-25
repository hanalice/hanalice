import os
import re
import random
import shutil
from datetime import datetime

# 配置
POSTS_DIR = './posts'
TAGS_DIR = './tags'
README_TEMPLATE = './README.template.md'
README_OUTPUT = './README.md'
MASCOTS_DIR = './assets/mascots'
DAILY_MASCOT = './assets/mascots/daily.gif'

def parse_post(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    meta = {}
    fm_match = re.search(r'^---\s*(.*?)\s*---', content, re.DOTALL)
    if fm_match:
        fm_content = fm_match.group(1)
        for line in fm_content.split('\n'):
            if ':' in line:
                key, val = line.split(':', 1)
                meta[key.strip().lower()] = val.strip()
    
    if 'title' not in meta:
        meta['title'] = os.path.basename(file_path).replace('.md', '')
    if 'date' not in meta:
        meta['date'] = '1970-01-01'
    if 'tags' not in meta:
        meta['tags'] = ''
        
    return {
        'title': meta['title'],
        'date': meta['date'],
        'tags': [t.strip() for t in meta['tags'].split(',') if t.strip()],
        'path': file_path
    }

def generate_tag_pages(all_tags, posts):
    """为每个标签生成一个独立的汇总页面"""
    if not os.path.exists(TAGS_DIR):
        os.makedirs(TAGS_DIR)
    
    # 清理旧的标签页
    for f in os.listdir(TAGS_DIR):
        if f.endswith('.md'):
            os.remove(os.path.join(TAGS_DIR, f))
    
    for tag, count in all_tags.items():
        tag_posts = [p for p in posts if tag in p['tags']]
        tag_posts.sort(key=lambda x: x['date'], reverse=True)
        
        content = f"# Posts Tagged With: #{tag}\n\n"
        content += f"Total: {count} posts\n\n"
        content += "---\n\n"
        for p in tag_posts:
            # 注意：路径需要从 tags/ 目录回退一级到根目录
            rel_path = f"../{p['path'].lstrip('./')}"
            content += f"- [{p['date']}] [{p['title']}]({rel_path})\n"
        
        content += "\n---\n[← Back to Home](../README.md)"
        
        tag_file = os.path.join(TAGS_DIR, f"{tag}.md")
        with open(tag_file, 'w', encoding='utf-8') as f:
            f.write(content)
    print(f"Generated {len(all_tags)} tag pages in {TAGS_DIR}")

def update_readme(posts, all_tags):
    if not os.path.exists(README_TEMPLATE):
        print(f"Error: {README_TEMPLATE} not found.")
        return

    with open(README_TEMPLATE, 'r', encoding='utf-8') as f:
        readme_content = f.read()

    # 1. 更新博文列表
    if posts:
        post_list_str = '\n'.join([f"- [{p['date']}] [{p['title']}]({p['path']})" for p in posts[:10]])
    else:
        post_list_str = "*暂时没有发布的博文，请在 /posts 目录下添加 Markdown 文件后自动同步。*"

    readme_content = re.sub(
        r'(<!-- BLOG-POST-LIST:START -->).*?(<!-- BLOG-POST-LIST:END -->)',
        f'\\1\n{post_list_str}\n\\2',
        readme_content,
        flags=re.DOTALL
    )

    # 2. 更新标签云 (链接到 tags/ 目录)
    if all_tags:
        tag_cloud_str = ' '.join([f"[`#{tag}({count})`](./tags/{tag}.md)" for tag, count in sorted(all_tags.items())])
    else:
        tag_cloud_str = "*暂无分类*"

    readme_content = re.sub(
        r'(<!-- TAG-CLOUD:START -->).*?(<!-- TAG-CLOUD:END -->)',
        f'\\1\n{tag_cloud_str}\n\\2',
        readme_content,
        flags=re.DOTALL
    )

    # 3. 更新健康度看板 (LAST_SYNC)
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    readme_content = readme_content.replace('{{LAST_SYNC}}', now_str)

    with open(README_OUTPUT, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print(f"Successfully updated {README_OUTPUT}")

def rotate_mascot():
    if not os.path.exists(MASCOTS_DIR):
        print("Mascots directory not found.")
        return
    
    mascots = [f for f in os.listdir(MASCOTS_DIR) if f.endswith(('.gif', '.png', '.jpg', '.webp')) and f != 'daily.gif' and f != 'default_mascot.png']
    if mascots:
        chosen = random.choice(mascots)
        shutil.copy(os.path.join(MASCOTS_DIR, chosen), DAILY_MASCOT)
        print(f"Updated mascot to: {chosen}")
    else:
        print("No mascots found in directory.")

if __name__ == '__main__':
    all_posts = []
    if os.path.exists(POSTS_DIR):
        for f in os.listdir(POSTS_DIR):
            if f.endswith('.md'):
                all_posts.append(parse_post(os.path.join(POSTS_DIR, f)))
    
    all_posts.sort(key=lambda x: x['date'], reverse=True)
    
    # 统计标签
    all_tags = {}
    for p in all_posts:
        for tag in p['tags']:
            all_tags[tag] = all_tags.get(tag, 0) + 1
            
    # 执行同步
    generate_tag_pages(all_tags, all_posts)
    update_readme(all_posts, all_tags)
    rotate_mascot()


