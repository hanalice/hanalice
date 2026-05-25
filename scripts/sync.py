import os
import sys
import random
import shutil
from datetime import datetime

POSTS_DIR = './posts'
TAGS_DIR = './tags'
README_TEMPLATE = './README.template.md'
README_OUTPUT = './README.md'
MASCOTS_DIR = './assets/mascots'


def parse_post(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    meta = {}
    lines = content.split('\n')
    if lines and lines[0].strip() == '---':
        try:
            end = lines[1:].index('---') + 1
        except ValueError:
            print(f"Warning: unclosed frontmatter in {file_path}, skipping.")
            return None
        for line in lines[1:end]:
            if ':' in line:
                key, val = line.split(':', 1)
                meta[key.strip().lower()] = val.strip()

    if 'title' not in meta:
        print(f"Warning: missing 'title' in {file_path}, skipping.")
        return None
    if 'date' not in meta:
        print(f"Warning: missing 'date' in {file_path}, skipping.")
        return None

    return {
        'title': meta['title'],
        'date': meta['date'],
        'tags': [t.strip() for t in meta.get('tags', '').split(',') if t.strip()],
        'path': file_path,
    }


def generate_tag_pages(all_tags, posts):
    if not all_tags:
        print("No tags found; skipping tag page generation to preserve existing files.")
        return

    if not os.path.exists(TAGS_DIR):
        os.makedirs(TAGS_DIR)

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
            rel_path = '../' + p['path'].removeprefix('./')
            content += f"- [{p['date']}] [{p['title']}]({rel_path})\n"

        content += "\n---\n[← Back to Home](../README.md)"

        tag_file = os.path.join(TAGS_DIR, f"{tag}.md")
        with open(tag_file, 'w', encoding='utf-8') as f:
            f.write(content)
    print(f"Generated {len(all_tags)} tag pages in {TAGS_DIR}")


def _inject_section(content, start_marker, end_marker, body):
    before, rest = content.split(start_marker, 1)
    _, after = rest.split(end_marker, 1)
    return before + start_marker + '\n' + body + '\n' + end_marker + after


def update_readme(posts, all_tags, daily_mascot=None):
    if not os.path.exists(README_TEMPLATE):
        sys.exit(f"Error: {README_TEMPLATE} not found.")

    with open(README_TEMPLATE, 'r', encoding='utf-8') as f:
        readme_content = f.read()

    if posts:
        post_list_str = '\n'.join(
            [f"- [{p['date']}] [{p['title']}]({p['path']})" for p in posts[:10]]
        )
    else:
        post_list_str = "*暂时没有发布的博文，请在 /posts 目录下添加 Markdown 文件后自动同步。*"

    readme_content = _inject_section(
        readme_content,
        '<!-- BLOG-POST-LIST:START -->',
        '<!-- BLOG-POST-LIST:END -->',
        post_list_str,
    )

    if all_tags:
        tag_cloud_str = ' '.join(
            [f"[`#{tag}({count})`](./tags/{tag}.md)" for tag, count in sorted(all_tags.items())]
        )
    else:
        tag_cloud_str = "*暂无分类*"

    readme_content = _inject_section(
        readme_content,
        '<!-- TAG-CLOUD:START -->',
        '<!-- TAG-CLOUD:END -->',
        tag_cloud_str,
    )

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    readme_content = readme_content.replace('{{LAST_SYNC}}', now_str)

    fallback_mascot = os.path.join(MASCOTS_DIR, 'default_mascot.png')
    readme_content = readme_content.replace('{{DAILY_MASCOT}}', daily_mascot or fallback_mascot)

    with open(README_OUTPUT, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print(f"Successfully updated {README_OUTPUT}")


def rotate_mascot():
    if not os.path.exists(MASCOTS_DIR):
        print("Mascots directory not found.")
        return None

    mascots = [
        f for f in os.listdir(MASCOTS_DIR)
        if f.endswith(('.gif', '.png', '.jpg', '.webp'))
        and not f.startswith('daily.')
        and f != 'default_mascot.png'
    ]
    if not mascots:
        print("No mascots found in directory.")
        return None

    chosen = random.choice(mascots)
    ext = os.path.splitext(chosen)[1]
    daily_name = 'daily' + ext
    dst = os.path.join(MASCOTS_DIR, daily_name)

    for f in os.listdir(MASCOTS_DIR):
        if f.startswith('daily.') and f != daily_name:
            os.remove(os.path.join(MASCOTS_DIR, f))

    shutil.copy(os.path.join(MASCOTS_DIR, chosen), dst)
    print(f"Updated mascot to: {chosen}")
    return dst


if __name__ == '__main__':
    all_posts = []
    if os.path.exists(POSTS_DIR):
        for f in os.listdir(POSTS_DIR):
            if f.endswith('.md'):
                post = parse_post(os.path.join(POSTS_DIR, f))
                if post is not None:
                    all_posts.append(post)

    all_posts.sort(key=lambda x: x['date'], reverse=True)

    all_tags = {}
    for p in all_posts:
        for tag in p['tags']:
            all_tags[tag] = all_tags.get(tag, 0) + 1

    generate_tag_pages(all_tags, all_posts)
    daily_mascot = rotate_mascot()
    update_readme(all_posts, all_tags, daily_mascot)
