"""
生成蜡笔小新风格的占位序列帧素材
角色特征：圆脸、粗眉毛、红色上衣、黄色短裤
仅保留 cheer 动画（2帧）
分辨率：128x128 PNG带alpha通道
"""
from PIL import Image, ImageDraw, ImageFilter
import math
import os
from pathlib import Path

BASE = Path(__file__).parent / "assets" / "animations"

# 确保目录存在
for anim in ["cheer"]:
    (BASE / anim).mkdir(parents=True, exist_ok=True)

# === 蜡笔小新配色 ===
SKIN = (255, 224, 189)       # 皮肤色
SKIN_SHADOW = (230, 200, 170)  # 皮肤阴影
HAIR = (60, 40, 30)           # 深棕色头发
EYEBROW = (30, 20, 15)        # 超粗黑眉毛
SHIRT_RED = (220, 60, 50)     # 红色上衣
SHORTS_YELLOW = (255, 200, 50) # 黄色短裤
SHOES = (50, 50, 60)          # 深色鞋子
WHITE = (255, 255, 255)
BLACK = (20, 20, 20)
CHEEK = (255, 180, 160)       # 腮红


def create_base(size=128):
    """创建透明底画布"""
    return Image.new("RGBA", (size, size), (0, 0, 0, 0))


def draw_xin_head(draw, cx, cy, scale=1.0, eye_offset=0, mouth_open=0.0, head_tilt=0.0):
    """画小新的头"""
    s = scale
    
    # 头部轮廓 - 土豆形
    head_w = int(42 * s)
    head_h = int(48 * s)
    
    # 画脸
    face_points = []
    for angle in range(0, 360, 5):
        rad = math.radians(angle + head_tilt)
        # 土豆形状：底部略平，顶部略扁
        r_x = head_w * (0.85 + 0.15 * math.cos(rad * 2))
        r_y = head_h * (0.9 + 0.1 * math.sin(rad * 2))
        px = cx + r_x * math.cos(rad)
        py = cy + r_y * math.sin(rad)
        face_points.append((px, py))
    
    draw.polygon(face_points, fill=SKIN, outline=(220, 190, 160), width=1)
    
    # 腮红
    blush_r = int(5 * s)
    draw.ellipse([cx - int(14*s) - blush_r, cy + int(2*s) - blush_r,
                  cx - int(14*s) + blush_r, cy + int(2*s) + blush_r], 
                 fill=CHEEK)
    draw.ellipse([cx + int(14*s) - blush_r, cy + int(2*s) - blush_r,
                  cx + int(14*s) + blush_r, cy + int(2*s) + blush_r], 
                 fill=CHEEK)
    
    # 眼睛 - 小新的小圆眼
    eye_y = cy - int(5 * s)
    eye_r = int(3.5 * s)
    eye_spacing = int(10 * s) + eye_offset
    
    # 左眼
    draw.ellipse([cx - eye_spacing - eye_r, eye_y - eye_r,
                  cx - eye_spacing + eye_r, eye_y + eye_r],
                 fill=BLACK)
    # 右眼
    draw.ellipse([cx + eye_spacing - eye_r, eye_y - eye_r,
                  cx + eye_spacing + eye_r, eye_y + eye_r],
                 fill=BLACK)
    
    # 瞳孔高光
    hl_r = int(1.2 * s)
    draw.ellipse([cx - eye_spacing - hl_r, eye_y - hl_r - 1,
                  cx - eye_spacing + hl_r, eye_y - hl_r + 1],
                 fill=WHITE)
    draw.ellipse([cx + eye_spacing - hl_r, eye_y - hl_r - 1,
                  cx + eye_spacing + hl_r, eye_y - hl_r + 1],
                 fill=WHITE)
    
    # 标志性的粗眉毛 - 在眼睛上方
    brow_y = eye_y - int(6 * s)
    brow_w = int(10 * s)
    brow_h = int(4 * s)
    
    # 左眉 - 粗且上扬
    draw.arc([cx - eye_spacing - brow_w, brow_y - brow_h,
              cx - eye_spacing + brow_w, brow_y + brow_h],
             0, 180, fill=EYEBROW, width=int(3 * s))
    # 右眉
    draw.arc([cx + eye_spacing - brow_w, brow_y - brow_h,
              cx + eye_spacing + brow_w, brow_y + brow_h],
             0, 180, fill=EYEBROW, width=int(3 * s))
    
    # 鼻子 - 小点
    nose_y = cy + int(3 * s)
    draw.pieslice([cx - int(2*s), nose_y - int(2*s),
                   cx + int(2*s), nose_y + int(2*s)],
                  0, 180, fill=(200, 170, 150))
    
    # 嘴巴
    mouth_y = cy + int(10 * s)
    if mouth_open > 0.3:
        # 张开的嘴
        mw = int(6 * s)
        mh = int(5 * s * mouth_open)
        draw.ellipse([cx - mw, mouth_y - mh//2, cx + mw, mouth_y + mh//2],
                     fill=(180, 80, 80))
    else:
        # 微笑
        draw.arc([cx - int(5*s), mouth_y - int(3*s),
                  cx + int(5*s), mouth_y + int(5*s)],
                 20, 160, fill=BLACK, width=int(1.5 * s))
    
    # 头发 - 顶部几撮
    hair_top = cy - int(24 * s)
    # 中间一撮
    draw.polygon([
        (cx - int(5*s), hair_top + int(3*s)),
        (cx, hair_top - int(8*s)),
        (cx + int(5*s), hair_top + int(3*s)),
    ], fill=HAIR)
    # 左边一撮
    draw.polygon([
        (cx - int(12*s), hair_top),
        (cx - int(10*s), hair_top - int(6*s)),
        (cx - int(7*s), hair_top + int(2*s)),
    ], fill=HAIR)
    # 右边一撮
    draw.polygon([
        (cx + int(7*s), hair_top + int(2*s)),
        (cx + int(10*s), hair_top - int(6*s)),
        (cx + int(12*s), hair_top),
    ], fill=HAIR)


def draw_body(draw, cx, cy, scale=1.0, arm_angle=0.0, leg_offset=0.0):
    """画小新的身体"""
    s = scale
    body_top = cy + int(24 * s)
    
    # 红色上衣
    shirt_w = int(20 * s)
    shirt_h = int(22 * s)
    shirt_points = [
        (cx - shirt_w, body_top),           # 左上
        (cx - shirt_w + int(3*s), body_top + int(8*s)),  # 左袖口
        (cx - shirt_w + int(5*s), body_top + shirt_h//2), # 左腰
        (cx - shirt_w + int(6*s), body_top + shirt_h),    # 左下
        (cx + shirt_w - int(6*s), body_top + shirt_h),    # 右下
        (cx + shirt_w - int(5*s), body_top + shirt_h//2), # 右腰
        (cx + shirt_w - int(3*s), body_top + int(8*s)),   # 右袖口
        (cx + shirt_w, body_top),           # 右上
    ]
    draw.polygon(shirt_points, fill=SHIRT_RED)
    
    # 衣领
    draw.polygon([
        (cx - int(6*s), body_top),
        (cx, body_top + int(5*s)),
        (cx + int(6*s), body_top),
    ], fill=(200, 50, 40))
    
    # 黄色短裤
    short_top = body_top + shirt_h - int(3*s)
    short_h = int(14 * s)
    short_w = int(18 * s)
    draw.polygon([
        (cx - short_w + int(3*s), short_top),
        (cx - short_w, short_top + short_h),
        (cx - int(4*s), short_top + short_h - int(3*s)),
        (cx + int(4*s), short_top + short_h - int(3*s)),
        (cx + short_w, short_top + short_h),
        (cx + short_w - int(3*s), short_top),
    ], fill=SHORTS_YELLOW)
    
    # 腿
    leg_top = short_top + short_h - int(5*s)
    leg_w = int(5 * s)
    leg_l = int(12 * s)
    
    # 左腿
    lx = cx - int(8 * s) + leg_offset
    draw.polygon([
        (lx - leg_w//2, leg_top),
        (lx - leg_w//2, leg_top + leg_l),
        (lx + leg_w//2, leg_top + leg_l),
        (lx + leg_w//2, leg_top),
    ], fill=SKIN)
    # 左鞋
    draw.rectangle([lx - leg_w//2 - 1, leg_top + leg_l - int(3*s),
                    lx + leg_w//2 + 1, leg_top + leg_l],
                   fill=SHOES)
    
    # 右腿
    rx = cx + int(8 * s) - leg_offset
    draw.polygon([
        (rx - leg_w//2, leg_top),
        (rx - leg_w//2, leg_top + leg_l),
        (rx + leg_w//2, leg_top + leg_l),
        (rx + leg_w//2, leg_top),
    ], fill=SKIN)
    # 右鞋
    draw.rectangle([rx - leg_w//2 - 1, leg_top + leg_l - int(3*s),
                    rx + leg_w//2 + 1, leg_top + leg_l],
                   fill=SHOES)
    
    # 手臂
    arm_len = int(14 * s)
    arm_w = int(4 * s)
    shoulder_y = body_top + int(6 * s)
    
    # 左臂
    la_x1 = cx - int(12 * s)
    la_x2 = la_x1 - int(arm_len * math.sin(arm_angle))
    la_y = shoulder_y + int(arm_len * math.cos(arm_angle))
    draw.line([(la_x1, shoulder_y), (la_x2, la_y)], 
              fill=SKIN, width=arm_w)
    # 左手
    draw.ellipse([la_x2 - int(3*s), la_y - int(3*s),
                  la_x2 + int(3*s), la_y + int(3*s)],
                 fill=SKIN)
    
    # 右臂
    ra_x1 = cx + int(12 * s)
    ra_x2 = ra_x1 + int(arm_len * math.sin(arm_angle))
    ra_y = shoulder_y + int(arm_len * math.cos(arm_angle))
    draw.line([(ra_x1, shoulder_y), (ra_x2, ra_y)], 
              fill=SKIN, width=arm_w)
    # 右手
    draw.ellipse([ra_x2 - int(3*s), ra_y - int(3*s),
                  ra_x2 + int(3*s), ra_y + int(3*s)],
                 fill=SKIN)




def generate_cheer_frames(output_dir, count=16):
    """生成cheer动画 - 欢呼跳跃"""
    for i in range(count):
        img = create_base()
        draw = ImageDraw.Draw(img)
        
        t = i / count * math.pi * 2
        
        cx, cy = 64, 45
        
        # 跳跃 - 正弦波
        jump = max(0, math.sin(t)) * 15
        
        # 手臂高举
        arm_ang = 2.5 - abs(math.sin(t)) * 0.5
        
        # 身体缩放 - 跳跃时拉长
        scale = 1.0 + 0.05 * math.sin(t)
        
        # 张嘴笑
        mouth = 0.5 + 0.5 * abs(math.sin(t))
        
        draw_body(draw, cx, cy - 24 + jump, scale=scale * 0.9,
                  arm_angle=arm_ang, leg_offset=math.sin(t)*2)
        draw_xin_head(draw, cx, cy - 24 + jump, scale=scale,
                      eye_offset=math.sin(t*3)*0.3,
                      mouth_open=mouth,
                      head_tilt=math.sin(t*0.5)*5)
        
        img.save(output_dir / f"frame_{i:03d}.png")
    print(f"Generated {count} cheer frames in {output_dir}")


if __name__ == "__main__":
    print("Generating Shin-chan style sprite frames...")
    
    generate_cheer_frames(BASE / "cheer", 2)
    
    print(f"\nDone! Generated 2 cheer frames.")
    print(f"Output directory: {BASE}")
