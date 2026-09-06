import os
import glob
import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageFilter, ImageOps
import numpy as np
import cv2

SOURCE_LOGO_PATH = '/tmp/dd259fe9-f85f-4574-af76-7d41e83cc0a0.png'
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

THEME_BG = (12, 14, 18) # #0c0e12 SmiTriX theme color

def make_squircle(img_rgb, radius_factor=0.22, border=True):
    """Takes a square RGB image and returns RGBA with rounded squircle corners."""
    W, H = img_rgb.size
    r = int(W * radius_factor)
    mask = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((0, 0, W-1, H-1), radius=r, fill=255)
    
    res = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    res.paste(img_rgb.convert('RGBA'), (0, 0), mask=mask)
    if border:
        d_res = ImageDraw.Draw(res)
        bw = max(1, int(W * 0.003))
        d_res.rounded_rectangle((bw, bw, W-1-bw, H-1-bw), radius=r, outline=(255, 255, 255, 36), width=bw)
    return res

def make_round(img_rgb):
    """Takes a square RGB image and returns circular RGBA."""
    W, H = img_rgb.size
    mask = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse((0, 0, W-1, H-1), fill=255)
    res = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    res.paste(img_rgb.convert('RGBA'), (0, 0), mask=mask)
    return res

def generate():
    print(f"Loading source logo: {SOURCE_LOGO_PATH}")
    src_im = Image.open(SOURCE_LOGO_PATH)
    
    # 1. Clean crop: remove top and bottom artifact bars (11px each)
    # y: 11 to 713
    arr_raw = np.array(src_im)[11:713, :]
    h_c, w_c, _ = arr_raw.shape
    
    # Logo barbell center: x=377, y=353
    cx, cy = 377, 353
    half = 349 # 698x698 square
    sq_arr = arr_raw[cy-half:cy+half, cx-half:cx+half].astype(np.float32)
    h_sq, w_sq, _ = sq_arr.shape
    
    # Feather the outer 48px to exactly THEME_BG so there are zero edge seams
    FEATHER = 48.0
    y_dist = np.minimum(np.arange(h_sq), h_sq - 1 - np.arange(h_sq))
    x_dist = np.minimum(np.arange(w_sq), w_sq - 1 - np.arange(w_sq))
    edge_dist = np.minimum(y_dist[:, None], x_dist[None, :])
    factor = np.clip(edge_dist / FEATHER, 0.0, 1.0)[:, :, None]
    
    target_bg_f = np.array(THEME_BG, dtype=np.float32)
    feathered_sq = sq_arr * factor + target_bg_f * (1.0 - factor)
    sq_img = Image.fromarray(feathered_sq.astype(np.uint8))
    
    # 2. Master dark canvases: 1024x1024 and 2048x2048
    # Logo scaled to ~80% of canvas
    def create_master_dark(canvas_sz):
        canvas = Image.new('RGB', (canvas_sz, canvas_sz), THEME_BG)
        scale = int(canvas_sz * 0.80)
        resized = sq_img.resize((scale, scale), Image.Resampling.LANCZOS)
        offset = (canvas_sz - scale) // 2
        canvas.paste(resized, (offset, offset))
        return canvas
    
    master_dark_1024 = create_master_dark(1024)
    master_dark_2048 = create_master_dark(2048)
    
    # Master squircle icons
    master_squircle_1024 = make_squircle(master_dark_1024)
    master_squircle_2048 = make_squircle(master_dark_2048)
    
    # Master transparent logo:
    # Key out background from master_dark_1024
    arr_1024 = np.array(master_dark_1024)
    is_logo = (arr_1024[:, :, 0] > 28) | (arr_1024[:, :, 1] > 32) | (arr_1024[:, :, 2] > 38)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (35, 35))
    closed = cv2.morphologyEx(is_logo.astype(np.uint8), cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    hull_mask = np.zeros((1024, 1024), dtype=np.uint8)
    for c in contours:
        if cv2.contourArea(c) > 5000:
            cv2.drawContours(hull_mask, [c], -1, 255, -1)
    smooth_mask = cv2.GaussianBlur(hull_mask, (15, 15), 0)
    master_trans_1024 = Image.fromarray(np.dstack([arr_1024, smooth_mask]))
    master_trans_2048 = master_trans_1024.resize((2048, 2048), Image.Resampling.LANCZOS)
    
    print("Generated master assets at 1024x1024 and 2048x2048")
    
    # 3. Save to assets/ folder
    os.makedirs(os.path.join(REPO_ROOT, 'assets'), exist_ok=True)
    master_trans_2048.save(os.path.join(REPO_ROOT, 'assets/logo.png'), optimize=True)
    master_squircle_2048.save(os.path.join(REPO_ROOT, 'assets/logo-squircle.png'), optimize=True)
    master_dark_2048.save(os.path.join(REPO_ROOT, 'assets/logo-dark.png'), optimize=True)
    master_squircle_1024.save(os.path.join(REPO_ROOT, 'assets/logo-1024.png'), optimize=True)
    master_squircle_1024.resize((512, 512), Image.Resampling.LANCZOS).save(os.path.join(REPO_ROOT, 'assets/logo-512.png'), optimize=True)
    print("Saved master logo assets in assets/")
    
    # 4. Web and PWA icons
    icon_512 = master_squircle_1024.resize((512, 512), Image.Resampling.LANCZOS)
    icon_180 = master_squircle_1024.resize((180, 180), Image.Resampling.LANCZOS)
    icon_trans_512 = master_trans_1024.resize((512, 512), Image.Resampling.LANCZOS)
    icon_trans_180 = master_trans_1024.resize((180, 180), Image.Resampling.LANCZOS)
    
    web_targets = [
        ('website/icon-512.png', icon_512),
        ('website/icon-180.png', icon_180),
        ('website/demo/icon-512.png', icon_512),
        ('website/demo/icon-180.png', icon_180),
        ('frontend/public/icon-512.png', icon_512),
        ('frontend/public/icon-180.png', icon_180),
        ('frontend/public/icon-transparent.png', icon_trans_512),
        ('frontend/public/logo-app.png', icon_trans_180),
        ('frontend/dist/icon-512.png', icon_512),
        ('frontend/dist/icon-180.png', icon_180),
        ('frontend/dist/icon-transparent.png', icon_trans_512),
        ('frontend/dist/logo-app.png', icon_trans_180),
        ('frontend/android/app/src/main/assets/public/icon-512.png', icon_512),
        ('frontend/android/app/src/main/assets/public/icon-180.png', icon_180),
    ]
    for rel, im in web_targets:
        full = os.path.join(REPO_ROOT, rel)
        if os.path.exists(os.path.dirname(full)):
            im.save(full, optimize=True)
            print("Saved web icon:", rel)
            
    # 5. Resources (icon.png and icon.svg)
    res_icon_png = os.path.join(REPO_ROOT, 'frontend/resources/icon.png')
    master_squircle_1024.save(res_icon_png, optimize=True)
    print("Saved resource icon:", res_icon_png)
    
    buf = BytesIO()
    master_squircle_1024.save(buf, format='PNG')
    b64_1024 = base64.b64encode(buf.getvalue()).decode('ascii')
    res_icon_svg = os.path.join(REPO_ROOT, 'frontend/resources/icon.svg')
    with open(res_icon_svg, 'w') as f:
        f.write(f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1024" height="1024" viewBox="0 0 1024 1024">
  <rect width="1024" height="1024" rx="225" fill="#0c0e12"/>
  <image xlink:href="data:image/png;base64,{b64_1024}" width="1024" height="1024"/>
</svg>
''')
    print("Saved resource icon SVG:", res_icon_svg)
    
    # 6. iOS AppIcon
    ios_icon_path = os.path.join(REPO_ROOT, 'frontend/ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-512@2x.png')
    if os.path.exists(os.path.dirname(ios_icon_path)):
        # iOS requires opaque icon without alpha
        master_dark_1024.convert('RGB').save(ios_icon_path, optimize=True)
        print("Saved iOS AppIcon:", ios_icon_path)
        
    # 7. Android Mipmap Icons
    # Android adaptive: background is solid THEME_BG, foreground has logo within safe zone
    densities = {
        'mipmap-ldpi': (36, 81),
        'mipmap-mdpi': (48, 108),
        'mipmap-hdpi': (72, 162),
        'mipmap-xhdpi': (96, 216),
        'mipmap-xxhdpi': (144, 324),
        'mipmap-xxxhdpi': (192, 432),
    }
    for folder, (legacy_sz, adaptive_sz) in densities.items():
        dir_path = os.path.join(REPO_ROOT, 'frontend/android/app/src/main/res', folder)
        if not os.path.exists(dir_path):
            continue
            
        # Background: solid THEME_BG
        bg_img = Image.new('RGBA', (adaptive_sz, adaptive_sz), (*THEME_BG, 255))
        bg_img.save(os.path.join(dir_path, 'ic_launcher_background.png'), optimize=True)
        
        # Foreground: logo in center (safe zone ~72%)
        fg_canvas = Image.new('RGBA', (adaptive_sz, adaptive_sz), (0, 0, 0, 0))
        logo_sz = int(adaptive_sz * 0.72)
        resized_fg = master_trans_1024.resize((logo_sz, logo_sz), Image.Resampling.LANCZOS)
        offset = (adaptive_sz - logo_sz) // 2
        fg_canvas.paste(resized_fg, (offset, offset), mask=resized_fg)
        fg_canvas.save(os.path.join(dir_path, 'ic_launcher_foreground.png'), optimize=True)
        
        # Legacy ic_launcher: squircle
        leg_icon = master_squircle_1024.resize((legacy_sz, legacy_sz), Image.Resampling.LANCZOS)
        leg_icon.save(os.path.join(dir_path, 'ic_launcher.png'), optimize=True)
        
        # Legacy ic_launcher_round: circle
        round_icon = make_round(master_dark_1024).resize((legacy_sz, legacy_sz), Image.Resampling.LANCZOS)
        round_icon.save(os.path.join(dir_path, 'ic_launcher_round.png'), optimize=True)
        
        print(f"Updated Android {folder}")
        
    # 8. Splash Screens
    # Android drawables + iOS Splash.imageset
    splash_targets = glob.glob(os.path.join(REPO_ROOT, 'frontend/android/app/src/main/res/drawable*/*.png')) + \
                     glob.glob(os.path.join(REPO_ROOT, 'frontend/ios/App/App/Assets.xcassets/Splash.imageset/*.png'))
                     
    for sp_path in splash_targets:
        try:
            im = Image.open(sp_path)
            W, H = im.size
            new_sp = Image.new('RGBA', (W, H), (*THEME_BG, 255))
            
            # Badge size: ~22% of min(W, H), clamped between 64 and 512
            badge_sz = max(64, min(512, int(min(W, H) * 0.22)))
            badge = master_squircle_1024.resize((badge_sz, badge_sz), Image.Resampling.LANCZOS)
            
            cx = (W - badge_sz) // 2
            cy = (H - badge_sz) // 2
            new_sp.paste(badge, (cx, cy), mask=badge)
            new_sp.save(sp_path, optimize=True)
        except Exception as e:
            print(f"Error on splash {sp_path}: {e}")
            
    print("Updated all splash screens")

if __name__ == '__main__':
    generate()
