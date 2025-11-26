import pygame
import math
import random

# --- 基础配置 ---
pygame.init()
WIDTH, HEIGHT = 1200, 800
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Entropy's Ark: The Complete Journey")
FONT = pygame.font.SysFont("Arial", 14, bold=True) # UI字体
BIG_FONT = pygame.font.SysFont("Arial", 30, bold=True)
CLOCK = pygame.time.Clock()

# --- 颜色定义 ---
COLOR_BG = (8, 8, 16)
COLOR_SUN = (255, 200, 50)
COLOR_SUN_COLONIZED = (50, 200, 255) # 殖民后变蓝
COLOR_ARK = (255, 255, 255)
COLOR_VELOCITY = (0, 255, 0)   # 绿色：惯性方向
COLOR_HEADING = (255, 50, 50)  # 红色：船头指向
COLOR_ZONE = (0, 100, 50)      # 宜居带圈

# --- 物理与游戏参数 ---
G = 1.0                # 引力常数
DT = 1.0               # 时间步长
ROT_SPEED = 0.08       # 旋转速度
THRUST_POWER = 0.15    # 引擎推力
COLONIZE_SPEED = 0.3   # 殖民进度增长速度
GEN_DISTANCE = 3000    # 生成新恒星的距离阈值

class Camera:
    def __init__(self):
        self.x, self.y = 0, 0
        self.scale = 0.5

    def w2s(self, wx, wy):
        return int((wx - self.x) * self.scale + WIDTH/2), int((wy - self.y) * self.scale + HEIGHT/2)

    def update(self, target_x, target_y):
        self.x += (target_x - self.x) * 0.05
        self.y += (target_y - self.y) * 0.05

class Star:
    def __init__(self, x, y, level=1):
        self.x, self.y = x, y
        self.level = level
        self.radius = random.randint(60, 90)
        self.mass = self.radius * 120 # 质量与半径成正比
        
        # 宜居带范围
        self.hz_min = self.radius * 4.0
        self.hz_max = self.radius * 7.0
        
        self.colonized = False
        self.progress = 0.0
        
        # 如果是初始恒星(level 0)，默认已殖民
        if level == 0:
            self.colonized = True
            self.progress = 100.0

    def draw(self, surface, cam):
        sx, sy = cam.w2s(self.x, self.y)
        r_scr = int(self.radius * cam.scale)
        
        # 绘制宜居带 (未殖民时显示)
        if not self.colonized:
            pygame.draw.circle(surface, COLOR_ZONE, (sx, sy), int(self.hz_max * cam.scale), 1)
            pygame.draw.circle(surface, COLOR_ZONE, (sx, sy), int(self.hz_min * cam.scale), 1)
        
        # 绘制恒星主体
        color = COLOR_SUN_COLONIZED if self.colonized else COLOR_SUN
        pygame.draw.circle(surface, color, (sx, sy), r_scr)
        
        # 绘制进度条
        if 0 < self.progress < 100:
            bar_w = 100 * cam.scale
            pygame.draw.rect(surface, (50, 0, 0), (sx - bar_w/2, sy + r_scr + 10, bar_w, 6))
            pygame.draw.rect(surface, (0, 255, 0), (sx - bar_w/2, sy + r_scr + 10, bar_w * (self.progress/100), 6))

class Ark:
    def __init__(self, start_star):
        # 1. 完美轨道初始化逻辑
        # 我们把飞船放在恒星上方 400 距离处
        orbit_dist = 450
        self.x = start_star.x
        self.y = start_star.y - orbit_dist
        
        # 计算该距离下的圆形轨道速度: v = sqrt(GM/r)
        v_orbit = math.sqrt(G * start_star.mass / orbit_dist)
        
        # 初始速度方向必须垂直于连线 (切向)
        # 位置在上方，所以速度向右(1, 0)
        self.vx = v_orbit
        self.vy = 0
        
        self.angle = 0 # 船头朝右
        self.mass = 10.0 # 飞船空重
        
        # --- 资源系统回归 ---
        self.energy = 500.0
        self.max_energy = 500.0
        self.fuel = 500.0
        self.matter = 200.0 # 采集到的物质
        
        self.solar_panels = 1
        
        self.alive = True
        self.msg = "System Online."

    def update(self, stars, keys):
        if not self.alive: return None, 0

        # --- 1. 操控 (牛顿力学) ---
        # 左右旋转船头
        if keys[pygame.K_LEFT]: self.angle -= ROT_SPEED
        if keys[pygame.K_RIGHT]: self.angle += ROT_SPEED
        
        is_thrusting = False
        # 向上推进
        if keys[pygame.K_UP]:
            if self.fuel > 0 and self.energy > 0:
                is_thrusting = True
                self.fuel -= 0.3 # 燃料消耗
                self.energy -= 0.1 # 引擎耗电
                
                # 沿船头方向施加推力
                ax = math.cos(self.angle) * THRUST_POWER
                ay = math.sin(self.angle) * THRUST_POWER
                self.vx += ax
                self.vy += ay
        
        # --- 2. 万有引力 (多体) ---
        nearest_star = None
        min_dist = float('inf')
        
        for star in stars:
            dx = star.x - self.x
            dy = star.y - self.y
            d_sq = dx*dx + dy*dy
            dist = math.sqrt(d_sq)
            
            # 记录最近恒星
            if dist < min_dist:
                min_dist = dist
                nearest_star = star
            
            # 碰撞检测
            if dist < star.radius + 10:
                self.alive = False
                self.msg = "CRITICAL: Crashed into Star"
                return nearest_star, min_dist

            # 引力计算 (只计算一定范围内的，优化体验)
            if dist < 5000:
                force = G * star.mass / d_sq
                acc = force / self.mass
                self.vx += acc * (dx / dist) * DT
                self.vy += acc * (dy / dist) * DT

        # --- 3. 物理位移 ---
        self.x += self.vx * DT
        self.y += self.vy * DT

        # --- 4. 资源循环 ---
        # 能量：靠近恒星回充，深空掉电
        if nearest_star:
            # 光照强度与距离平方成反比
            flux = (nearest_star.mass / 10) / (min_dist**2 + 1) * 2000 
            # 只有活着的恒星(或刚殖民的)才给能量，这里假设所有恒星都发光
            energy_gain = flux * self.solar_panels * 0.1
            self.energy += energy_gain
        
        self.energy -= 0.2 # 基础维生消耗
        if self.energy > self.max_energy: self.energy = self.max_energy
        
        if self.energy <= 0:
            self.alive = False
            self.msg = "FAILURE: Energy Depleted (Frozen)"

        return nearest_star, min_dist

    def draw(self, surface, cam, thrusting):
        if not self.alive: return
        sx, sy = cam.w2s(self.x, self.y)
        
        # 辅助线：红色船头
        head_x = sx + math.cos(self.angle) * 40 * cam.scale
        head_y = sy + math.sin(self.angle) * 40 * cam.scale
        pygame.draw.line(surface, COLOR_HEADING, (sx, sy), (head_x, head_y), 2)
        
        # 辅助线：绿色速度矢量
        vel_mag = math.sqrt(self.vx**2 + self.vy**2)
        if vel_mag > 0.1:
            end_x = sx + self.vx * 10 * cam.scale
            end_y = sy + self.vy * 10 * cam.scale
            pygame.draw.line(surface, COLOR_VELOCITY, (sx, sy), (end_x, end_y), 2)

        # 飞船本体
        size = 20 * cam.scale
        p1 = (sx + math.cos(self.angle)*size, sy + math.sin(self.angle)*size)
        p2 = (sx + math.cos(self.angle + 2.5)*size, sy + math.sin(self.angle + 2.5)*size)
        p3 = (sx + math.cos(self.angle - 2.5)*size, sy + math.sin(self.angle - 2.5)*size)
        pygame.draw.polygon(surface, COLOR_ARK, [p1, p2, p3])
        
        if thrusting:
            pygame.draw.circle(surface, (100, 200, 255), (int(sx), int(sy)), int(8*cam.scale))

class GameWorld:
    def __init__(self):
        self.camera = Camera()
        # 初始星球 (Level 0, 已殖民)
        self.stars = [Star(0, 0, level=0)]
        self.ark = Ark(self.stars[0])
        self.colonized_count = 1
        self.target_colonies = 5
        self.max_dist_gen = 0 # 记录探索最远距离

    def update(self):
        keys = pygame.key.get_pressed()
        
        # 1. 飞船更新
        thrusting = keys[pygame.K_UP] and self.ark.fuel > 0
        near_star, dist = self.ark.update(self.stars, keys)
        
        if not self.ark.alive: return

        # 2. 摄像机
        self.camera.update(self.ark.x, self.ark.y)
        
        # 3. 建设指令 (资源交换)
        # [1] 造电池/扩容能量
        if keys[pygame.K_1]:
            if self.ark.matter >= 50:
                self.ark.matter -= 50
                self.ark.max_energy += 100
                self.ark.msg = "Battery Upgraded."
        
        # [2] 造燃料 (重要!)
        if keys[pygame.K_2]:
            if self.ark.matter >= 20 and self.ark.energy >= 50:
                self.ark.matter -= 20
                self.ark.energy -= 50
                self.ark.fuel += 50
                self.ark.msg = "Fuel Synthesized."

        # 4. 殖民逻辑
        if near_star and not near_star.colonized:
            # 条件：在宜居带内 (Hz_min < dist < Hz_max) 且 速度较慢 (Speed < 3.0)
            speed = math.sqrt(self.ark.vx**2 + self.ark.vy**2)
            in_zone = near_star.hz_min < dist < near_star.hz_max
            
            if in_zone and speed < 3.0:
                near_star.progress += COLONIZE_SPEED
                self.ark.msg = f"Colonizing... {int(near_star.progress)}%"
                
                # 殖民成功
                if near_star.progress >= 100:
                    near_star.colonized = True
                    self.colonized_count += 1
                    # 奖励：补给大量物资
                    self.ark.matter += 200
                    self.ark.fuel += 200
                    self.ark.energy = self.ark.max_energy
                    self.ark.msg = "Colonization Complete! Supplies Added."
            elif in_zone:
                self.ark.msg = "Too Fast to Colonize! Slow Down!"
            else:
                # 离开区域进度缓慢衰减
                if near_star.progress > 0:
                    near_star.progress -= 0.1

        # 5. 无限宇宙生成
        # 计算离原点距离
        dist_from_origin = math.sqrt(self.ark.x**2 + self.ark.y**2)
        if dist_from_origin > self.max_dist_gen + GEN_DISTANCE:
            self.max_dist_gen = dist_from_origin
            self.spawn_new_star()

    def spawn_new_star(self):
        # 在玩家移动的前方扇形区域生成
        angle = math.atan2(self.ark.vy, self.ark.vx)
        gen_angle = angle + random.uniform(-0.5, 0.5)
        gen_dist = random.uniform(2000, 3000)
        
        new_x = self.ark.x + math.cos(gen_angle) * gen_dist
        new_y = self.ark.y + math.sin(gen_angle) * gen_dist
        
        self.stars.append(Star(new_x, new_y, level=len(self.stars)))
        self.ark.msg = "New Star System Detected."

    def draw(self, screen):
        # 1. 恒星 (带有提示箭头)
        min_d = float('inf')
        target_s = None
        
        for s in self.stars:
            s.draw(screen, self.camera)
            # 寻找最近的未殖民恒星作为目标提示
            if not s.colonized:
                d = (s.x - self.ark.x)**2 + (s.y - self.ark.y)**2
                if d < min_d:
                    min_d = d
                    target_s = s
        
        # 2. 飞船
        keys = pygame.key.get_pressed()
        self.ark.draw(screen, self.camera, keys[pygame.K_UP] and self.ark.fuel > 0)
        
        # 3. 目标指示箭头
        if target_s:
            sx, sy = self.camera.w2s(target_s.x, target_s.y)
            # 如果目标在屏幕外，画箭头
            if sx < 0 or sx > WIDTH or sy < 0 or sy > HEIGHT:
                ang = math.atan2(target_s.y - self.ark.y, target_s.x - self.ark.x)
                cx, cy = WIDTH/2, HEIGHT/2
                arrow_x = cx + math.cos(ang) * 350
                arrow_y = cy + math.sin(ang) * 350
                pygame.draw.circle(screen, (255, 50, 50), (int(arrow_x), int(arrow_y)), 8)

        # 4. UI 面板
        self.draw_ui(screen)

    def draw_ui(self, screen):
        # 资源条绘制
        def draw_bar(x, y, val, max_val, color, name):
            pygame.draw.rect(screen, (30, 30, 30), (x, y, 150, 15))
            ratio = max(0, min(1, val / max_val))
            pygame.draw.rect(screen, color, (x, y, 150 * ratio, 15))
            txt = FONT.render(f"{name}: {int(val)}", True, (200, 200, 200))
            screen.blit(txt, (x + 160, y))

        draw_bar(20, 20, self.ark.energy, self.ark.max_energy, (0, 200, 255), "Energy")
        draw_bar(20, 45, self.ark.fuel, 1000, (255, 150, 0), "Fuel")
        draw_bar(20, 70, self.ark.matter, 1000, (150, 150, 150), "Matter")

        # 状态信息
        info = [
            f"Colonies: {self.colonized_count}/{self.target_colonies}",
            f"Speed: {math.sqrt(self.ark.vx**2 + self.ark.vy**2):.2f}",
            f"System: {self.ark.msg}"
        ]
        for i, txt in enumerate(info):
            s = BIG_FONT if i == 0 else FONT
            col = (0, 255, 0) if i == 0 else (200, 200, 200)
            screen.blit(s.render(txt, True, col), (20, 100 + i*25))

        # 操作提示
        guides = [
            "CONTROLS (ENGLISH INPUT ONLY):",
            "[LEFT/RIGHT] Rotate Ship (Red Line)",
            "[UP] Thrust (Towards Red Line)",
            "[1] Upgrade Battery (-50 Matter)",
            "[2] Synthesize Fuel (-20 Matter, -50 Energy)",
            "GOAL: Stay in Green Zone of new stars to colonize."
        ]
        h = HEIGHT - 140
        for i, g in enumerate(guides):
            screen.blit(FONT.render(g, True, (150, 150, 150)), (20, h + i*20))

        if self.colonized_count >= self.target_colonies:
            win_txt = BIG_FONT.render("VICTORY! NEW CIVILIZATION ESTABLISHED.", True, (0, 255, 0))
            screen.blit(win_txt, (WIDTH/2 - 250, HEIGHT/2))

        if not self.ark.alive:
            fail_txt = BIG_FONT.render("GAME OVER. PRESS 'R' TO RESTART", True, (255, 50, 50))
            screen.blit(fail_txt, (WIDTH/2 - 250, HEIGHT/2))

def main():
    world = GameWorld()
    running = True
    
    while running:
        SCREEN.fill(COLOR_BG)
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r and not world.ark.alive:
                    world = GameWorld()
        
        world.update()
        world.draw(SCREEN)
        
        pygame.display.flip()
        CLOCK.tick(60)
        
    pygame.quit()

if __name__ == "__main__":
    main()