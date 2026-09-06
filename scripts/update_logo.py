import os
import glob
import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageOps

SOURCE_LOGO_PATH = '/tmp/f882c8d1-77d3-447e-9ebe-25937bc35895.png'
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def main():
    print("Loading source logo:", SOURCE_LOGO_PATH)
    src_raw = Image.open(SOURCE_LOGO_PATH).convert('RGB')
    
    # Pad source image slightly (8%) so it sits comfortably inside any frame / mask
    # 2000 -> 2000 with logo taking up central ~84%
    PAD_FACTOR = 0.08
    def make_padded_logo(target_size):
        canvas = Image.new('RGBA', (target_size, target_size), (255, 255, 255, 255))
        inner_sz = int(target_size * (1 - 2 * PAD_FACTOR))
        resized = src_raw.resize((inner_sz, inner_sz), Image.Resampling.LANCZOS).convert('RGBA')
        offset = (target_size - inner_sz) // 2
        canvas.paste(resized, (offset, offset))
        return canvas

    # 1. PWA & Web Icons (512x512 and 180x180)
    logo_512 = make_padded_logo(512)
    logo_180 = make_padded_logo(180)
    logo_1024 = make_padded_logo(1024)

    web_512_targets = [
        'website/icon-512.png',
        'website/demo/icon-512.png',
        'frontend/public/icon-512.png',
        'frontend/dist/icon-512.png',
        'frontend/android/app/src/main/assets/public/icon-512.png',
    ]
    web_180_targets = [
        'website/icon-180.png',
        'website/demo/icon-180.png',
        'frontend/public/icon-180.png',
        'frontend/dist/icon-180.png',
        'frontend/android/app/src/main/assets/public/icon-180.png',
    ]

    for rel in web_512_targets:
        full = os.path.join(REPO_ROOT, rel)
        if os.path.exists(os.path.dirname(full)):
            logo_512.save(full)
            print("Saved:", rel)

    for rel in web_180_targets:
        full = os.path.join(REPO_ROOT, rel)
        if os.path.exists(os.path.dirname(full)):
            logo_180.save(full)
            print("Saved:", rel)

    # 2. Master source icon & iOS AppIcon
    ios_icon_path = os.path.join(REPO_ROOT, 'frontend/ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-512@2x.png')
    if os.path.exists(os.path.dirname(ios_icon_path)):
        logo_1024.convert('RGB').save(ios_icon_path)
        print("Saved iOS AppIcon:", ios_icon_path)

    res_icon_png = os.path.join(REPO_ROOT, 'frontend/resources/icon.png')
    logo_1024.save(res_icon_png)
    print("Saved resource icon:", res_icon_png)

    # Base64 for SVG
    buf = BytesIO()
    logo_1024.save(buf, format='PNG')
    b64_1024 = base64.b64encode(buf.getvalue()).decode('ascii')
    res_icon_svg = os.path.join(REPO_ROOT, 'frontend/resources/icon.svg')
    with open(res_icon_svg, 'w') as f:
        f.write(f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1024" height="1024" viewBox="0 0 1024 1024">
  <rect width="1024" height="1024" fill="#ffffff"/>
  <image xlink:href="data:image/png;base64,{b64_1024}" width="1024" height="1024"/>
</svg>
''')
    print("Saved resource icon SVG:", res_icon_svg)

    # 3. Android Mipmap Icons
    # For legacy ic_launcher and ic_launcher_round, preserve original alpha mask from existing file
    # For ic_launcher_foreground: white canvas with safe-zone scaled logo
    # For ic_launcher_background: solid white
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

        # Background (solid white)
        bg_img = Image.new('RGBA', (adaptive_sz, adaptive_sz), (255, 255, 255, 255))
        bg_img.save(os.path.join(dir_path, 'ic_launcher_background.png'))

        # Foreground: adaptive_sz with safe zone logo
        # In Android adaptive icon with 16.7% inset in XML:
        # We place logo inside adaptive_sz
        fg_img = make_padded_logo(adaptive_sz)
        fg_img.save(os.path.join(dir_path, 'ic_launcher_foreground.png'))

        # Legacy ic_launcher:
        legacy_path = os.path.join(dir_path, 'ic_launcher.png')
        if os.path.exists(legacy_path):
            old_im = Image.open(legacy_path)
            old_alpha = old_im.getchannel('A')
            new_leg = make_padded_logo(legacy_sz)
            new_leg.putalpha(old_alpha)
            new_leg.save(legacy_path)

        # Legacy ic_launcher_round:
        round_path = os.path.join(dir_path, 'ic_launcher_round.png')
        if os.path.exists(round_path):
            old_im = Image.open(round_path)
            old_alpha = old_im.getchannel('A')
            new_rd = make_padded_logo(legacy_sz)
            new_rd.putalpha(old_alpha)
            new_rd.save(round_path)

        print(f"Updated Android {folder}")

    # 4. Splash Screens
    # Android drawables and iOS Assets.xcassets/Splash.imageset
    splash_targets = glob.glob(os.path.join(REPO_ROOT, 'frontend/android/app/src/main/res/drawable*/*.png')) + \
                     glob.glob(os.path.join(REPO_ROOT, 'frontend/ios/App/App/Assets.xcassets/Splash.imageset/*.png'))

    for sp_path in splash_targets:
        try:
            im = Image.open(sp_path)
            W, H = im.size
            # Dark background #0c0e12
            new_sp = Image.new('RGBA', (W, H), (12, 14, 18, 255))

            # Tile size: ~18% of min(W, H), clamped between 48 and 420
            tile_sz = max(48, min(420, int(min(W, H) * 0.18)))
            tile_r = int(tile_sz * 0.22)

            tile = Image.new('RGBA', (tile_sz, tile_sz), (0, 0, 0, 0))
            t_mask = Image.new('L', (tile_sz, tile_sz), 0)
            t_draw = ImageDraw.Draw(t_mask)
            t_draw.rounded_rectangle((0, 0, tile_sz-1, tile_sz-1), radius=tile_r, fill=255)

            pad = max(2, int(tile_sz * 0.05))
            inner_sz = tile_sz - 2 * pad
            logo_inner = src_raw.resize((inner_sz, inner_sz), Image.Resampling.LANCZOS).convert('RGBA')

            tile_white = Image.new('RGBA', (tile_sz, tile_sz), (255, 255, 255, 255))
            tile_white.paste(logo_inner, (pad, pad))
            tile.paste(tile_white, (0, 0), mask=t_mask)

            # Center on canvas
            cx = (W - tile_sz) // 2
            cy = (H - tile_sz) // 2
            new_sp.paste(tile, (cx, cy), mask=tile)
            new_sp.save(sp_path)
        except Exception as e:
            print(f"Error on splash {sp_path}: {e}")

    print("Updated all splash screens")

    # 5. Banners
    # assets/banner.png and website/img/banner.png (1320x380)
    BW, BH = 1320, 380
    banner = Image.new('RGBA', (BW, BH), (0, 0, 0, 0))

    # Background rounded rectangle
    bg_mask = Image.new('L', (BW, BH), 0)
    d_mask = ImageDraw.Draw(bg_mask)
    d_mask.rounded_rectangle((0, 0, BW-1, BH-1), radius=44, fill=255)

    grad = Image.new('RGBA', (BW, BH))
    r1, g1, b1 = 18, 21, 27
    r2, g2, b2 = 12, 14, 18
    for y in range(BH):
        t = y / BH
        r = int(r1 * (1 - t) + r2 * t)
        g = int(g1 * (1 - t) + g2 * t)
        b = int(b1 * (1 - t) + b2 * t)
        for x in range(BW):
            grad.putpixel((x, y), (r, g, b, 255))

    banner.paste(grad, (0, 0), mask=bg_mask)

    d_ban = ImageDraw.Draw(banner)
    d_ban.rounded_rectangle((3, 3, BW-4, BH-4), radius=42, outline=(43, 49, 64, 255), width=4)

    # Logo tile
    tile_sz = 240
    tile_r = 52
    tile = Image.new('RGBA', (tile_sz, tile_sz), (0, 0, 0, 0))
    t_mask = Image.new('L', (tile_sz, tile_sz), 0)
    t_draw = ImageDraw.Draw(t_mask)
    t_draw.rounded_rectangle((0, 0, tile_sz-1, tile_sz-1), radius=tile_r, fill=255)

    pad = 12
    inner_sz = tile_sz - 2 * pad
    logo_inner = src_raw.resize((inner_sz, inner_sz), Image.Resampling.LANCZOS).convert('RGBA')

    tile_white = Image.new('RGBA', (tile_sz, tile_sz), (255, 255, 255, 255))
    tile_white.paste(logo_inner, (pad, pad))
    tile.paste(tile_white, (0, 0), mask=t_mask)

    t_draw_tile = ImageDraw.Draw(tile)
    t_draw_tile.rounded_rectangle((0, 0, tile_sz-1, tile_sz-1), radius=tile_r, outline=(255, 255, 255, 40), width=3)

    tile_x = 110
    tile_y = (BH - tile_sz) // 2
    banner.paste(tile, (tile_x, tile_y), mask=tile)

    # Typography
    font_title = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 110)
    font_sub = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 38)
    font_tags = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 26)

    text_x = 420
    title_y = 65

    d_ban.text((text_x, title_y), 'Smi', font=font_title, fill=(238, 241, 246, 255))
    smi_bbox = d_ban.textbbox((text_x, title_y), 'Smi', font=font_title)
    trix_x = smi_bbox[2]
    d_ban.text((trix_x, title_y), 'TriX', font=font_title, fill=(163, 230, 53, 255))

    sub_y = title_y + 125
    d_ban.text((text_x + 4, sub_y), 'Self-hosted gym & body-weight tracker', font=font_sub, fill=(139, 148, 167, 255))

    tags_y = sub_y + 60
    d_ban.text((text_x + 4, tags_y), 'passkey login  ·  own your data  ·  docker  ·  AGPL', font=font_tags, fill=(92, 100, 117, 255))

    banner_targets = [
        'assets/banner.png',
        'website/img/banner.png',
    ]
    for rel in banner_targets:
        full = os.path.join(REPO_ROOT, rel)
        if os.path.exists(os.path.dirname(full)):
            banner.save(full)
            print("Saved banner:", rel)

    # Also update assets/banner.svg
    buf = BytesIO()
    tile.save(buf, format='PNG')
    b64_tile = base64.b64encode(buf.getvalue()).decode('ascii')
    banner_svg_path = os.path.join(REPO_ROOT, 'assets/banner.svg')
    with open(banner_svg_path, 'w') as f:
        f.write(f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="660" height="190" viewBox="0 0 660 190" role="img" aria-label="SmiTriX — gym &amp; body-weight tracker">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#12151b"/>
      <stop offset="1" stop-color="#0c0e12"/>
    </linearGradient>
  </defs>
  <rect width="660" height="190" rx="22" fill="url(#bg)"/>
  <rect x="1.5" y="1.5" width="657" height="187" rx="20.5" fill="none" stroke="#2b3140" stroke-width="3"/>

  <!-- SmiTriX logo badge -->
  <image xlink:href="data:image/png;base64,{b64_tile}" x="55" y="35" width="120" height="120"/>

  <!-- wordmark + tagline -->
  <text x="214" y="86" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,DejaVu Sans,Helvetica,Arial,sans-serif" font-size="62" font-weight="800" letter-spacing="-2">
    <tspan fill="#eef1f6">Smi</tspan><tspan fill="#a3e635">TriX</tspan>
  </text>
  <text x="216" y="120" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,DejaVu Sans,Helvetica,Arial,sans-serif" font-size="20.5" font-weight="600" fill="#8b94a7">Self-hosted gym &amp; body-weight tracker</text>
  <text x="216" y="146" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,DejaVu Sans,Helvetica,Arial,sans-serif" font-size="14" font-weight="500" fill="#5c6475">passkey login  ·  own your data  ·  docker  ·  AGPL</text>
</svg>
''')
    print("Saved banner SVG:", banner_svg_path)

if __name__ == '__main__':
    main()
