"""
陶瓷材料文献 - 实体关系提取脚本 (v3 并发优化版)
优化点:
  1. ThreadPoolExecutor 块级并发 — 每篇论文多块同时调 API
  2. ThreadPoolExecutor 论文级并发 — 同时处理 3 篇论文
  3. CHUNK_SIZE 提升到 12000 — 减少分块数
  4. 文本预清洗 — 去噪声、压缩空白
  5. 移除 sleep — 并发控制自带节流

用法: python ceramic_extract_v3.py <results_dir> [--workers 3] [--chunk-size 12000]
"""
import os
import re
import json
import time
import sys
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from openai import OpenAI

# ── 配置 ──
API_KEY = os.getenv("API_KEY", "sk-6daa6d75b15f467db7cce6523a235d15")
BASE_URL = os.getenv("BASE_URL", "https://api.deepseek.com")
MODEL = os.getenv("MODEL_NAME", "deepseek-chat")

client = OpenAI(api_key=API_KEY, base_url=BASE_URL, timeout=300)
CHUNK_SIZE = 12000  # 比 v2 大 50%
MAX_WORKERS_PER_PAPER = 5  # 每篇论文内并发块数
MAX_WORKERS_PAPERS = 3      # 同时处理的论文数

print_lock = Lock()

def log(*args, **kwargs):
    with print_lock:
        print(*args, **kwargs)


# ═══════════════════════════════════════════
# Windows 长路径处理 (>260字符)
# ═══════════════════════════════════════════

def long_path(path: str) -> str:
    """Windows 扩展路径前缀，绕过 260 字符限制"""
    if os.name == 'nt':
        abs_path = os.path.abspath(path)
        if len(abs_path) > 260 and not abs_path.startswith('\\\\?\\'):
            return '\\\\?\\' + abs_path
        return abs_path
    return path


def long_open(path: str, mode: str = 'r', **kwargs):
    """支持长路径的 open()"""
    return open(long_path(path), mode, **kwargs)

# ═══════════════════════════════════════════
# Prompt 模板（中文版）
# ═══════════════════════════════════════════

ENTITY_PROMPT = """你是一位精通陶瓷材料科学的领域专家。请从以下论文文本中提取所有关键科学实体，构建陶瓷材料知识图谱。

## 实体类型（共8类，type字段必须填写中文）：

### 1. 材料
涵盖：陶瓷基体、掺杂元素/化合物、第二相/增强相、电极材料、靶材、磨料。
保留化学式原始写法，精确到大小写、上下标和LaTeX格式（如Pb(Zr_{0.47}Ti_{0.53})O_3）。

常见材料体系：
- 压电/铁电陶瓷：BaTiO3(BT), Pb(Zr,Ti)O3(PZT), (Bi0.5Na0.5)TiO3(BNT), (K0.5Na0.5)NbO3(KNN), BiFeO3(BFO), (Ba,Ca)(Zr,Ti)O3(BCZT), Pb(Mg1/3Nb2/3)O3-PbTiO3(PMN-PT), Pb(In1/2Nb1/2)O3-PbTiO3(PIN-PT), BiScO3-PbTiO3(BS-PT), LiNbO3, LiTaO3
- 无铅压电体系：BNT-BT, BNT-BT-KNN, BNT-BKT, KNN-LiSbO3, Ba(Zr0.2Ti0.8)O3-0.5(Ba0.7Ca0.3)TiO3(BZT-BCT)
- 反铁电体：PbZrO3, AgNbO3, NaNbO3, (Pb,La)(Zr,Sn,Ti)O3(PLZST)
- 弛豫铁电体：Pb(Mg1/3Nb2/3)O3(PMN), (Pb,La)(Zr,Ti)O3(PLZT)
- 微波介质陶瓷：Ba(Zn1/3Ta2/3)O3, Ba(Mg1/3Ta2/3)O3, CaTiO3-NdAlO3, Zn2SiO4
- 结构陶瓷：SiC, Si3N4, Al2O3, ZrO2(YSZ), TiB2, TiC, B4C, WC, Ti3SiC2, Ti3AlC2(MAX相)
- 固体电解质/离子导体：YSZ, Gd掺杂CeO2(GDC), La1-xSrxGa1-yMgyO3(LSGM), Li7La3Zr2O12(LLZO), NaSICON
- 透明陶瓷：Y3Al5O12(YAG), AlON, MgAl2O4, Tb3Ga5O12(TGG)
- 生物陶瓷：羟基磷灰石(HA), β-TCP, 生物活性玻璃
- 磁性陶瓷：NiZnFe2O4, MnZnFe2O4, BaFe12O19, Y3Fe5O12(YIG), La1-xSrxMnO3
- 掺杂元素/离子：La3+, Nb5+, Mn2+/Mn4+, Fe3+, Er3+, Sm3+, Gd3+, Yb3+, Ce4+, Cu2+, Li+, Ta5+, Sb5+, Ni2+, Co2+/Co3+
- 烧结助剂/添加剂：CuO, MnO2, Li2CO3, SiO2, MgO, V2O5, Bi2O3, ZnO, B2O3
- 第二相/增强相：碳纳米管(CNT/MWCNT), 石墨烯, 纳米银(Ag), Pt, 碳纤维, SiC晶须
- 玻璃相/助熔剂：硼硅酸盐玻璃, K2O-B2O3-SiO2
- 电极材料：Ag, Pt, Au, Ag-Pd, 银浆, LaNiO3, SrRuO3(SRO)

### 2. 性能
不包含具体数值（数值归入"性能指标"），描述材料的物理化学性质。

- 电学性能：介电常数(ε'/εr), 介电损耗(tanδ), 压电系数d33/d31/d15, 机电耦合系数kp/kt/k33, 电导率(σ), 电阻率(ρ), 介电击穿强度(Eb/BDS), 铁电极化(Pr/Ps/Pm/Ec), 可调性(tunability), 漏电流密度, 阻抗, 电容
- 储能相关：储能密度(Wrec/Wtotal), 储能效率(η), 功率密度(PD), 充放电时间(t0.9), 放电能量密度(WD)
- 热学性能：热导率(κ), 热膨胀系数(CTE), 居里温度(Tc), 比热容(Cp), 热稳定性, 退极化温度(Td), 熔点(Tm), 弛豫-铁电相变温度(TF-R)
- 力学性能：抗弯强度(σf), 断裂韧性(KIC), 维氏硬度(Hv), 杨氏模量(E), 压缩强度, 剪切模量(G), 泊松比(ν), 磨损率, 弹性模量
- 光学性能：透过率(T%), 折射率(n), 光学带隙(Eg), 光致发光(PL), 上转换发光, 吸收系数(α), 消光比
- 磁学性能：饱和磁化强度(Ms), 剩余磁化强度(Mr), 矫顽力(Hc), 磁电耦合系数(αME), 磁导率(μ), 居里温度(Tc_M), 磁损耗, 自旋-声子耦合
- 抗辐照性能：抗非晶化能力, 辐照肿胀率, 缺陷聚集速率, 位移阈能(Ed), dpa容限
- 其他：相对密度, 表观孔隙率, 晶粒尺寸(d), 活化能(Ea), 频率色散(Δf), 老化速率, 机械品质因数(Qm/Qf), 品质因数(Q×f)

### 3. 制备工艺
涵盖粉体合成、成型、烧结、后处理全流程。

- 粉体制备：固相反应法(固相法), 溶胶-凝胶法(sol-gel), 水热法(hydrothermal), 共沉淀法(co-precipitation), 熔盐法(molten salt synthesis), 高能球磨, 自蔓延高温合成(SHS), 喷雾干燥, 冷冻干燥, 化学气相沉积(CVD), 脉冲激光沉积(PLD)
- 成型工艺：干压成型(uniaxial pressing), 冷等静压(CIP), 流延成型(tape casting), 注浆成型(slip casting), 注射成型, 3D打印/增材制造, 凝胶注模(gel casting)
- 烧结工艺：无压烧结, 热压烧结(HP), 放电等离子烧结/等离子活化烧结(SPS/PAS), 微波烧结, 两步烧结(TSS), 闪烧(flash sintering), 冷烧结(CSP), 气氛烧结, 真空烧结
- 薄膜/涂层制备：磁控溅射, 脉冲激光沉积(PLD), 溶胶-凝胶旋涂, 丝网印刷, 电子束蒸镀, 原子层沉积(ALD), 金属有机化学气相沉积(MOCVD)
- 后处理：退火/热处理, 极化(poling), 热极化, 交流极化, 研磨, 抛光, 激光切割/加工, 淬火(quenching), 炉冷(furnace cooling)

### 4. 应用领域
- 电子元件：多层陶瓷电容器(MLCC), 片式电感, 压敏电阻, 热敏电阻(NTC/PTC), 微波介质谐振器/滤波器/天线, 基板/封装
- 能量器件：介电储能电容器, 固态氧化物燃料电池(SOFC), 锂电池固态电解质, 钠硫电池电解质, 太阳能电池, 温差发电, 超级电容器
- 传感器/驱动器：压电传感器, 超声换能器, 压电驱动器/致动器, 加速度计, 陀螺仪, 声表面波(SAW)器件, 磁电传感器, 气体传感器, 温度传感器
- 机械/结构：切削刀具, 耐磨部件, 热障涂层(TBC), 环境障涂层(EBC), 装甲防护, 轴承, 密封件
- 光学：红外窗口/整流罩, 激光增益介质, 荧光粉基质, LED荧光体, 磁光隔离器, 闪烁体, 电光开关
- 生物医学：骨修复/骨替代, 牙科修复材料, 药物缓释载体, 生物植入体
- 核能/航天：核反应堆结构材料, 中子吸收材料, 辐照屏蔽材料, 高温结构件, 热防护系统(TPS)
- 其他：催化剂/催化载体, 磁性制冷, 电卡制冷, 水分解电极, 电磁屏蔽, 吸波材料

### 5. 微观结构
涵盖晶体结构、缺陷化学、显微组织。

- 晶体结构/相：钙钛矿结构(perovskite ABO3), 尖晶石结构(spinel AB2O4), 萤石结构(fluorite), 钛铁矿结构(ilmenite), 烧绿石结构(pyrochlore), 钨青铜结构, Aurivillius相, MAX相(Mn+1AXn), 石榴石结构(garnet)
- 相组成/对称性：四方相(T-phase), 三方相(R-phase), 立方相(C-phase), 单斜相(M-phase), 正交相(O-phase), 准同型相界(MPB), 多晶型相界(PPB), 多相共存
- 显微组织：晶粒(grain), 晶界(grain boundary), 畴壁(domain wall), 铁电畴(ferroelectric domain), 极性纳米微区(PNRs), 气孔(pore/porosity), 致密化(densification), 核壳结构(core-shell), 析出相(precipitate), 第二相(secondary phase), 织构(texture), 层状结构
- 缺陷化学：氧空位(V_O¨/Vo), 阳离子空位(V_A'/V_B'), 缺陷偶极子(defect dipole), 缺陷复合体(defect complex), 受主掺杂(acceptor doping), 施主掺杂(donor doping), 反位缺陷(antisite defect), 间隙原子(interstitial), 位错(dislocation), 堆垛层错(stacking fault), 弗伦克尔缺陷(Frenkel), 肖特基缺陷(Schottky)
- 有序/无序：长程有序, 短程有序, B位阳离子有序, 成分起伏/波动, 化学序

### 6. 表征方法
- 结构表征：X射线衍射(XRD), 同步辐射XRD, Rietveld精修, 中子衍射, 电子背散射衍射(EBSD), 选区电子衍射(SAED), 劳厄衍射
- 形貌/成分：扫描电子显微镜(SEM), 透射电子显微镜(TEM), 高分辨TEM(HRTEM), 扫描透射电镜(STEM), 高角环形暗场像(HAADF-STEM), 能量色散X射线谱(EDS/EDX), 电子探针(EPMA), 原子力显微镜(AFM), 压电力显微镜(PFM), 扫描隧道显微镜(STM)
- 光谱/能谱：X射线光电子能谱(XPS), 紫外光电子能谱(UPS), 拉曼光谱(Raman), 傅里叶变换红外光谱(FTIR), 电子顺磁共振(EPR/ESR), 核磁共振(NMR), X射线吸收精细结构(XAFS/EXAFS/XANES), 穆斯堡尔谱, 俄歇电子能谱(AES)
- 热分析：差示扫描量热法(DSC), 热重分析(TGA/TG), 热机械分析(TMA), 热膨胀仪(DIL), 激光闪射法(LFA)
- 电学测试：阻抗分析仪(Impedance Spectroscopy/EIS), 铁电分析仪(P-E loop/电滞回线), d33测试仪(Berlincourt), 精密LCR表, 高阻计, 击穿强度测试, I-V特性测试, 热激励去极化电流(TSDC)
- 力学测试：维氏压痕法(Vickers indentation), 万能试验机, 动态力学分析(DMA), 纳米压痕, 阿基米德法(Archimedes method, 密度测量)
- 计算模拟：第一性原理/密度泛函理论(DFT), 分子动力学(MD), 有限元模拟(FEM), 相场模拟(Phase-field), 蒙特卡洛模拟(Monte Carlo), GGA/PBE/PW91(交换关联泛函), 投影缀加平面波(PAW), VASP/CASTEP/Gaussian(计算软件), 态密度(DOS/PDOS/TDOS), 能带结构, 声子谱/声子色散, 形成能, 缺陷形成能

### 7. 性能指标
每个量化数据点单独提取为一个实体。数值+单位+条件必须保留在name中。

- 格式规范：
  * "d33 = 450 pC/N"
  * "居里温度 = 386°C"
  * "储能密度Wrec = 3.90 J/cm³ (at 280 kV/cm)"
  * "KIC = 5.2 MPa·m¹/²"
  * "晶粒尺寸 = 2.5 μm"
  * "Pr = 32 μC/cm², Ec = 5.2 kV/mm"
  * "可调性 = 35% (at 30 kV/cm)"
  * "抗弯强度 = 520 MPa"
  * "$2P_r = 66 \\mu C/cm^2$"

- 带条件的指标特别重要：如"在280 kV/cm电场下储能密度 = 3.90 J/cm³"
- 比较性数据也需提取："掺杂后d33从320提升至450 pC/N"

### 8. 合成参数
- 烧结相关：烧结温度, 保温时间, 升温速率, 降温速率, 烧结气氛(N2/O2/Ar/真空/还原), 烧结压力
- 粉体处理：球磨时间, 球磨转速, 球料比, 煅烧温度, 煅烧时间, 预烧温度
- 极化条件：极化电场强度, 极化温度, 极化时间, 极化介质(硅油/空气)
- 薄膜参数：沉积温度, 衬底温度, 溅射功率, 靶基距, 工作气压, 氧分压
- 掺杂量：如"1 at.% Fe掺杂", "0.5 wt.% MnO2添加", "x = 0.15 BaTiO3含量"
- 退火条件：退火温度, 退火时间, 退火气氛, 淬火介质

## 提取规则（重要！）：
1. 化学式保留原文写法，精确到大小写、上下标和LaTeX格式。对含LaTeX的（如$\\mathrm{BaTiO_3}$）提取纯文本形式BaTiO3
2. context字段必须引用原文原句30-120字作为证据，要求准确
3. 缩写与全称合并策略：以最完整的化学式为准，在attributes中标注缩写（如PZT→Pb(Zr,Ti)O3, attributes含"缩写":"PZT"）
4. 提取粒度：宁可多提不可漏提。每类实体独立提取，不要合并不同概念
5. 掺杂变体：同一材料的每种掺杂配方分别提取（如"Fe掺杂BNT-BT"和"Mn掺杂BNT-BT"各自独立）
6. 性能指标必须保留"数值+单位+条件"的完整形式，每个具体数值一个独立实体
7. 论文类型适配：
   - 实验论文：重点提取材料、工艺参数、性能数据、表征手段
   - 计算/理论论文：重点提取计算模型、泛函方法、模拟参数、缺陷类型、形成能
8. 缺陷化学实体：氧空位、缺陷偶极子、反位缺陷等应归为"微观结构"

## 示例输出：
{{
  "entities": [
    {{"name": "Pb(Zr0.47Ti0.53)O3", "type": "材料", "attributes": {{"缩写": "PZT", "分类": "压电陶瓷"}}, "context": "addition of small amounts (below 0.1 wt. %) of multi-walled carbon nanotubes (MWCNTs) to Pb(Zr0.47Ti0.53)O3 (PZT) ceramics prepared by spark plasma sintering"}},
    {{"name": "MWCNT", "type": "材料", "attributes": {{"角色": "第二相/增强相", "全称": "多壁碳纳米管"}}, "context": "addition of small amounts (below 0.1 wt. %) of multi-walled carbon nanotubes (MWCNTs)"}},
    {{"name": "放电等离子烧结", "type": "制备工艺", "attributes": {{"缩写": "SPS"}}, "context": "Pb(Zr0.47Ti0.53)O3 (PZT) ceramics prepared by spark plasma sintering"}},
    {{"name": "0.1 wt.% MWCNT添加", "type": "合成参数", "attributes": {{"掺杂量": "0.1 wt.%"}}, "context": "addition of small amounts (below 0.1 wt. %) of multi-walled carbon nanotubes"}},
    {{"name": "介电常数", "type": "性能", "attributes": {{}}, "context": "The reduction of dielectric constant with increasing CNTs additions"}},
    {{"name": "可调性", "type": "性能", "attributes": {{}}, "context": "small increase of tunability was explained by the increasing internal field"}},
    {{"name": "介电常数随CNT增加而降低", "type": "性能指标", "attributes": {{"趋势": "降低"}}, "context": "The reduction of dielectric constant with increasing CNTs additions, together with the small increase of tunability"}},
    {{"name": "钙钛矿结构", "type": "微观结构", "attributes": {{}}, "context": "XRD patterns show perovskite phase in all sintered ceramics"}},
    {{"name": "氧空位", "type": "微观结构", "attributes": {{"符号": "Vo"}}, "context": "oxygen vacancies created for charge compensation form defect complexes"}},
    {{"name": "缺陷复合体", "type": "微观结构", "attributes": {{"组成": "Fe_Ti'-Vo"}}, "context": "formation of (Fe_Ti'-Vo) defect complexes in the Fe-doped material"}},
    {{"name": "SEM", "type": "表征方法", "attributes": {{"全称": "扫描电子显微镜"}}, "context": "microstructure of sintered samples was investigated by scanning electron microscopy"}},
    {{"name": "EPR", "type": "表征方法", "attributes": {{"全称": "电子顺磁共振", "频率": "X-Band 9.86 GHz"}}, "context": "X-Band (9.86 GHz) EPR spectra were collected at 22 °C using a Bruker EMX Spectrometer"}},
    {{"name": "密度泛函理论", "type": "表征方法", "attributes": {{"缩写": "DFT", "泛函": "GGA-PW91"}}, "context": "First-principles calculations are performed based on density functional theory (DFT) in the generalized gradient approximation (GGA) with the functional of Perdew and Wang (PW91)"}}
  ]
}}

## 论文文本：
__TEXT__

仅返回JSON，不要任何解释："""

RELATION_PROMPT = """你是陶瓷材料知识图谱专家。基于已提取的实体列表，发现并提取实体间的所有科学关系。

## 关系类型（共10类，relation字段必须填中文）：
**重要：relation字段只能从以下10种中选择，禁止使用"合成参数""应用领域""制备工艺""密度"等实体类型名称！**

### 1. 具有性能
材料 → 性能
该材料具备的性能属性（电学/力学/热学/光学/磁学等）。
多值举例：PZT同时具有"压电系数d33""介电常数""居里温度"等。
- 基体材料→性能、掺杂材料→性能、复合材料→性能均可

### 2. 采用工艺
材料 → 制备工艺
该材料通过什么工艺制备或加工。
- 粉体→煅烧工艺、陶瓷→烧结工艺、薄膜→沉积工艺

### 3. 应用于
材料 → 应用领域
该材料在什么领域有应用或潜在应用。
- 涵盖已商业化和潜在/建议的应用

### 4. 具有结构
材料 → 微观结构
该材料具有的晶体结构、相组成、显微组织、缺陷特征。
- 如：PZT→钙钛矿结构、BCZT→四方相+C立方相共存、BNT-BT→极性纳米微区(PNRs)
- 缺陷类结构（氧空位、缺陷偶极子、反位缺陷）也使用此关系

### 5. 表征方法
材料/性能/微观结构 → 表征方法
用什么实验手段或计算方法来表征/测量/分析该实体。
- 如：晶体结构→XRD、畴结构→PFM、缺陷化学→EPR、电子结构→DFT计算、元素价态→XPS

### 6. 性能指标
性能 → 性能指标
将抽象性能链接到具体量化数值。
- 如：压电系数d33→d33 = 450 pC/N、居里温度→Tc = 386°C
- 一个性能可以有多个性能指标（不同条件/不同样品/不同温度下）

### 7. 掺杂元素
材料（基体/主相）→ 材料（掺杂剂）
基体材料掺杂了什么元素或化合物。方向：基体 → 掺杂剂。
- 如：PZT→MnO2、BNT-BT→Fe2O3、BCZT→Sm2O3
- 掺杂浓度信息放在attributes中标注

### 8. 影响关系
制备工艺/材料/掺杂元素/合成参数 → 性能
某因素对性能产生了影响。在attributes标注"增强/提高"或"降低/抑制"。
- 如：MnO2掺杂→d33（提高）、晶粒细化→介电常数（降低）
- 淬火→剩余极化（增大）、退火温度升高→氧空位浓度（减少）

### 9. 含有组分
材料（复合体系/固溶体）→ 材料（组元/端元）
复合材料、固溶体、多层结构中含有什么组分。
- 如：BNT-BT→BNT、BNT-BT→BT、PZT-PMN→PZT
- BCZT-SM→BCZT、BCZT-SM→BiSmO3

### 10. 合成条件
制备工艺 → 合成参数
制备工艺的具体参数条件。
- 如：固相反应法→煅烧温度900°C、SPS烧结→烧结温度1150°C、极化→极化电场6 kV/mm
- 退火→退火温度450°C、球磨→球磨时间24h

## 提取规则（重要！）：
1. **精确匹配**：关系的head和tail必须与"已识别实体"列表中的name完全一致（含标点、空格）。参考实体列表中的 [编号] name (类型) 来选择
2. **evidence准确性**：必须引用原文中支持该关系的实际句子，30-150字
3. **性能-指标链接**：每个性能指标必须通过"性能指标"关系链接到对应性能；一个性能可以有多个指标
4. **方向规范**：
   - 掺杂元素：基体→掺杂剂（PZT→MnO2）
   - 含有组分：复合体系→组元（BCZT-SM→BCZT）
   - 影响关系：因素→结果（掺杂→性能变化）
   - 合成条件：工艺→参数（烧结→烧结温度）
5. **关系完整性**：每个实体应至少参与一个关系（孤立实体需要标记），核心材料应有多条关系
6. **attributes补充**：影响关系在attributes中注明"正面/负面"或具体趋势；掺杂关系可注明掺杂量
7. **避免冗余**：同一(head, relation, tail)三元组只出现一次；如果同一关系在不同证据段都出现，选最完整的那条evidence
8. **实验vs计算论文**：
   - 实验论文：重点提取工艺→材料、材料→性能、性能→指标、掺杂→性能影响
   - 计算论文：重点提取计算方法→材料/缺陷、缺陷→形成能、结构→态密度/能带、材料→抗辐照等预测性能

## 示例输出：
{{
  "relations": [
    {{"head": "Pb(Zr0.47Ti0.53)O3", "relation": "掺杂元素", "tail": "MWCNT", "evidence": "addition of small amounts (below 0.1 wt. %) of multi-walled carbon nanotubes (MWCNTs) to Pb(Zr0.47Ti0.53)O3 (PZT) ceramics", "attributes": {{"掺杂量": "0.1 wt.%"}}}},
    {{"head": "Pb(Zr0.47Ti0.53)O3", "relation": "采用工艺", "tail": "放电等离子烧结", "evidence": "Pb(Zr0.47Ti0.53)O3 (PZT) ceramics prepared by spark plasma sintering"}},
    {{"head": "Pb(Zr0.47Ti0.53)O3", "relation": "具有性能", "tail": "介电常数", "evidence": "The reduction of dielectric constant with increasing CNTs additions"}},
    {{"head": "Pb(Zr0.47Ti0.53)O3", "relation": "具有性能", "tail": "可调性", "evidence": "small increase of tunability was explained by the increasing internal field"}},
    {{"head": "MWCNT", "relation": "影响关系", "tail": "介电常数", "evidence": "The reduction of dielectric constant with increasing CNTs additions", "attributes": {{"趋势": "降低"}}}},
    {{"head": "MWCNT", "relation": "影响关系", "tail": "可调性", "evidence": "small increase of tunability", "attributes": {{"趋势": "提高"}}}},
    {{"head": "Pb(Zr0.47Ti0.53)O3", "relation": "具有结构", "tail": "钙钛矿结构", "evidence": "XRD patterns show perovskite phase in all sintered ceramics"}},
    {{"head": "Pb(Zr0.47Ti0.53)O3", "relation": "表征方法", "tail": "SEM", "evidence": "microstructure of sintered samples was investigated by scanning electron microscopy (SEM)"}},
    {{"head": "Pb(Zr0.47Ti0.53)O3", "relation": "表征方法", "tail": "拉曼光谱", "evidence": "results of the Raman study suggest that the low employed sintering temperatures allowed the CNT structures to survive"}},
    {{"head": "放电等离子烧结", "relation": "合成条件", "tail": "0.1 wt.% MWCNT添加", "evidence": "addition of small amounts of MWCNTs to PZT ceramics prepared by spark plasma sintering"}},
    {{"head": "BNT-BT:Fe", "relation": "具有结构", "tail": "氧空位", "evidence": "acceptor-doping creates oxygen vacancies, which in the course of aging diffuse to lower energy lattice sites"}},
    {{"head": "BNT-BT:Fe", "relation": "具有结构", "tail": "缺陷复合体", "evidence": "EPR spectra indicate the existence of (Fe_Ti'-Vo) defect complexes in the Fe-doped material"}},
    {{"head": "BNT-BT:Fe", "relation": "表征方法", "tail": "EPR", "evidence": "X-Band (9.86 GHz) EPR spectra were collected at 22 °C using a Bruker EMX Spectrometer"}},
    {{"head": "缺陷复合体", "relation": "表征方法", "tail": "密度泛函理论", "evidence": "simulated spectra of defect complexes formed by Fe3+ and oxygen vacancies are shown for comparison"}},
    {{"head": "Ti3SiC2", "relation": "具有结构", "tail": "MAX相", "evidence": "Ti3SiC2 and Ti3AlC2 are layered ternary carbides belong to the so-called MAX phase"}},
    {{"head": "Ti3SiC2", "relation": "表征方法", "tail": "密度泛函理论", "evidence": "First-principles calculations are performed based on DFT in the GGA with the functional of PW91"}}
  ]
}}

## 已识别实体：
__ENTITIES__

## 论文文本：
__TEXT__

仅返回JSON，不要任何解释："""


# ═══════════════════════════════════════════
# 文本预处理
# ═══════════════════════════════════════════

def clean_text(text: str) -> str:
    """文本预清洗：去噪声、压缩空白"""
    # 去掉过短行（通常是页眉页脚/页码）
    lines = text.split('\n')
    lines = [l for l in lines if len(l.strip()) > 3 or l.strip() == '']
    # 合并连续空白行
    text = '\n'.join(lines)
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    # 去掉引用标记 [1], [2,3] 等（保留在 context 里但减少干扰）
    # 不在这里做，避免误删
    return text.strip()


# ═══════════════════════════════════════════
# JSON 修复（同 v2）
# ═══════════════════════════════════════════

def repair_json(raw: str) -> str:
    """修复常见 LLM 输出 JSON 错误"""
    raw = raw.strip()

    # 去掉 markdown 代码块
    m = re.search(r'```(?:json)?\s*(.*?)\s*```', raw, re.DOTALL)
    if m:
        raw = m.group(1).strip()
    else:
        s = raw.find('{')
        e = raw.rfind('}')
        if s >= 0 and e > s:
            raw = raw[s:e+1]

    # 修复: 缺少逗号 (换行处)
    raw = re.sub(r'"\s*\n\s*"', '",\n  "', raw)
    raw = re.sub(r'\}\s*\n\s*\{', '},\n{', raw)
    raw = re.sub(r'\]\s*\n\s*\[', '],\n[', raw)
    # 修复: 尾随逗号
    raw = re.sub(r',\s*}', '}', raw)
    raw = re.sub(r',\s*]', ']', raw)
    # 修复: 未闭合括号
    open_braces = raw.count('{') - raw.count('}')
    open_brackets = raw.count('[') - raw.count(']')
    if open_braces > 0:
        raw += '}' * open_braces
    if open_brackets > 0:
        raw += ']' * open_brackets

    return raw


def safe_json_parse(raw: str, data_type: str = "entities"):
    """安全解析 JSON，失败返回空结构"""
    repaired = repair_json(raw)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    # 最后手段：正则提取
    result = {}
    if data_type == "entities":
        names = re.findall(r'"name"\s*:\s*"([^"]*)"', raw)
        types = re.findall(r'"type"\s*:\s*"([^"]*)"', raw)
        contexts = re.findall(r'"context"\s*:\s*"([^"]*)"', raw)
        entities = []
        for i, n in enumerate(names):
            entities.append({
                "name": n,
                "type": types[i] if i < len(types) else "",
                "context": contexts[i] if i < len(contexts) else ""
            })
        result["entities"] = entities
    elif data_type == "relations":
        heads = re.findall(r'"head"\s*:\s*"([^"]*)"', raw)
        tails = re.findall(r'"tail"\s*:\s*"([^"]*)"', raw)
        relations = re.findall(r'"relation"\s*:\s*"([^"]*)"', raw)
        evidences = re.findall(r'"evidence"\s*:\s*"([^"]*)"', raw)
        rels = []
        for i, r in enumerate(relations):
            rels.append({
                "head": heads[i] if i < len(heads) else "",
                "relation": r,
                "tail": tails[i] if i < len(tails) else "",
                "evidence": evidences[i] if i < len(evidences) else ""
            })
        result["relations"] = rels

    return result


# ═══════════════════════════════════════════
# 实体去重
# ═══════════════════════════════════════════

def normalize_name(name: str) -> str:
    return re.sub(r'[^a-z0-9一-鿿]', '', name.strip().lower())


def merge_entities(all_entities: list) -> list:
    merged = []
    seen = {}

    for e in all_entities:
        if not e.get("name"):
            continue
        norm = normalize_name(e["name"])
        if norm in seen:
            idx = seen[norm]
            if len(e.get("context", "")) > len(merged[idx].get("context", "")):
                merged[idx]["context"] = e["context"]
            if e.get("attributes"):
                if "attributes" not in merged[idx]:
                    merged[idx]["attributes"] = {}
                merged[idx]["attributes"].update(e["attributes"])
        else:
            seen[norm] = len(merged)
            merged.append(e)

    return merged


# LLM 有时会输出实体类型名而非关系类型，自动纠正
RELATION_TYPE_FIX = {
    "合成参数": "合成条件",
    "应用领域": "应用于",
    "制备工艺": "采用工艺",
    "密度": "性能指标",
}

def merge_relations(all_relations: list) -> list:
    seen = set()
    unique = []
    for r in all_relations:
        rel = r.get("relation", "")
        # 自动纠正非法关系类型
        if rel in RELATION_TYPE_FIX:
            r["relation"] = RELATION_TYPE_FIX[rel]
            rel = r["relation"]
        key = (r.get("head",""), rel, r.get("tail",""))
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


# ═══════════════════════════════════════════
# LLM 调用（带重试）
# ═══════════════════════════════════════════

def call_llm(prompt: str, max_retry: int = 3) -> str:
    for attempt in range(max_retry):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            content = resp.choices[0].message.content
            if content is None:
                log(f"    ⚠ API返回空content (finish_reason={resp.choices[0].finish_reason})")
                return ""
            return content.strip()
        except Exception as e:
            err_msg = str(e)[:150]
            wait = 2 ** attempt
            log(f"    ⚠ API异常 (尝试{attempt+1}/{max_retry}): {err_msg}")
            if attempt < max_retry - 1:
                time.sleep(wait)
    return ""


# ═══════════════════════════════════════════
# 分块
# ═══════════════════════════════════════════

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> list:
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    paragraphs = text.split('\n')
    current = ""
    for para in paragraphs:
        if len(current) + len(para) < chunk_size:
            current += para + '\n'
        else:
            if current:
                chunks.append(current.strip())
            current = para + '\n'
    if current.strip():
        chunks.append(current.strip())
    return chunks


# ═══════════════════════════════════════════
# 并发提取（核心优化）
# ═══════════════════════════════════════════

def extract_one_chunk_entities(chunk: str, chunk_idx: int, total_chunks: int) -> list:
    """提取单个块的实体（供并发调用）"""
    raw = call_llm(ENTITY_PROMPT.replace("__TEXT__", chunk))
    if not raw:
        return []
    result = safe_json_parse(raw, "entities")
    entities = result.get("entities", [])
    return [e for e in entities if isinstance(e, dict) and e.get("name")]


def extract_one_chunk_relations(chunk: str, entities_str: str, chunk_idx: int, total_chunks: int) -> list:
    """提取单个块的关系（供并发调用）"""
    prompt = RELATION_PROMPT.replace("__ENTITIES__", entities_str).replace("__TEXT__", chunk)
    raw = call_llm(prompt)
    if not raw:
        return []
    result = safe_json_parse(raw, "relations")
    relations = result.get("relations", [])
    return [r for r in relations if isinstance(r, dict)
            and r.get("head") and r.get("relation") and r.get("tail")]


def extract_entities_chunked(text: str) -> list:
    """并发分块提取实体"""
    chunks = chunk_text(text)
    if len(chunks) == 1:
        entities = extract_one_chunk_entities(chunks[0], 0, 1)
        return merge_entities(entities)

    all_entities = []
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS_PER_PAPER, len(chunks))) as executor:
        futures = {
            executor.submit(extract_one_chunk_entities, chunk, i, len(chunks)): i
            for i, chunk in enumerate(chunks)
        }
        for future in as_completed(futures):
            i = futures[future]
            try:
                entities = future.result()
                all_entities.extend(entities)
                log(f"    块 {i+1}/{len(chunks)} → {len(entities)}实体")
            except Exception as e:
                log(f"    块 {i+1}/{len(chunks)} ❌ {e}")

    return merge_entities(all_entities)


def extract_relations_chunked(entities: list, text: str) -> list:
    """并发分块提取关系"""
    if not entities:
        return []

    entities_str = "\n".join(
        f"- [{i}] {e.get('name','?')} ({e.get('type','?')})"
        for i, e in enumerate(entities) if e.get('name')
    )

    chunks = chunk_text(text)
    if len(chunks) == 1:
        relations = extract_one_chunk_relations(chunks[0], entities_str, 0, 1)
        return merge_relations(relations)

    all_relations = []
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS_PER_PAPER, len(chunks))) as executor:
        futures = {
            executor.submit(extract_one_chunk_relations, chunk, entities_str, i, len(chunks)): i
            for i, chunk in enumerate(chunks)
        }
        for future in as_completed(futures):
            i = futures[future]
            try:
                relations = future.result()
                all_relations.extend(relations)
                log(f"    块 {i+1}/{len(chunks)} → {len(relations)}关系")
            except Exception as e:
                log(f"    块 {i+1}/{len(chunks)} ❌ {e}")

    return merge_relations(all_relations)


# ═══════════════════════════════════════════
# 单篇处理
# ═══════════════════════════════════════════

def process_one_paper(paper_dir: str) -> dict:
    """处理单篇论文"""
    title = os.path.basename(paper_dir)
    out_path = os.path.join(paper_dir, "extracted.json")

    # 找 md 文件（列出目录避免长路径拼接）
    md_file = ""
    json_file = ""
    for f in os.listdir(paper_dir):
        if f.endswith(".md") and not md_file:
            md_file = f
        if f.endswith(".json") and f not in ("meta.json", "extracted.json") and not json_file:
            json_file = f

    # 读取文本（使用 long_open 绕过长路径限制）
    text = ""
    if md_file:
        md_path = os.path.join(paper_dir, md_file)
        try:
            with long_open(md_path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            log(f"  ⚠ 读取md失败: {e}")

    # md 太短时补 json
    if json_file and (not text or len(text) < 500):
        json_path = os.path.join(paper_dir, json_file)
        try:
            with long_open(json_path, "r", encoding="utf-8") as f:
                jdata = json.load(f)
            for block in jdata:
                if isinstance(block, dict) and block.get("text"):
                    text += block["text"] + "\n"
        except Exception as e:
            log(f"  ⚠ 读取json失败: {e}")

    if not text or len(text.strip()) < 200:
        return {"error": f"text too short ({len(text.strip())} chars)", "title": title}

    text = clean_text(text)
    chunks = chunk_text(text)
    log(f"  文本: {len(text)}字符, {len(chunks)}块")

    # 1. 并发提取实体
    t0 = time.time()
    entities = extract_entities_chunked(text)
    t1 = time.time()
    log(f"  实体: {len(entities)}个 ({t1-t0:.1f}s)")

    # 2. 并发提取关系
    relations = extract_relations_chunked(entities, text)
    t2 = time.time()
    log(f"  关系: {len(relations)}个 ({t2-t1:.1f}s)")

    result = {
        "title": title,
        "entities": entities,
        "relations": relations,
        "entity_count": len(entities),
        "relation_count": len(relations),
        "elapsed_s": round(t2 - t0, 1),
    }

    with long_open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


# ═══════════════════════════════════════════
# 批量处理（论文级并发）
# ═══════════════════════════════════════════

def batch_process(results_dir: str, workers: int = MAX_WORKERS_PAPERS, chunk_size: int = CHUNK_SIZE, force: bool = False):
    global CHUNK_SIZE
    CHUNK_SIZE = chunk_size

    papers = []
    skipped_existing = 0
    for item in sorted(os.listdir(results_dir)):
        paper_dir = os.path.join(results_dir, item)
        if not os.path.isdir(paper_dir):
            continue
        if not force and os.path.exists(os.path.join(paper_dir, "extracted.json")):
            skipped_existing += 1
            continue
        has_content = any(f.endswith(".md") or f.endswith(".json")
                         for f in os.listdir(paper_dir))
        if not has_content:
            continue
        papers.append(paper_dir)

    total = len(papers)
    log(f"待处理: {total} 篇" + (f" (跳过已抽取: {skipped_existing})" if skipped_existing else ""))
    log(f"并发论文数: {workers}")
    log(f"分块大小: {CHUNK_SIZE}")
    if force:
        log("⚠ --force: 将覆盖已有的 extracted.json")
    log("=" * 50)

    if total == 0:
        log("全部完成！")
        return

    completed = 0
    failed = 0
    start_all = time.time()

    # 论文级并发
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_paper = {
            executor.submit(process_one_paper, paper_dir): (i, paper_dir)
            for i, paper_dir in enumerate(papers)
        }

        for future in as_completed(future_to_paper):
            i, paper_dir = future_to_paper[future]
            title = os.path.basename(paper_dir)[:70]

            try:
                result = future.result()
                if "error" in result:
                    failed += 1
                    log(f"[{i+1}/{total}] {title} ⚠ {result['error']}")
                else:
                    completed += 1
                    elapsed_total = time.time() - start_all
                    rate = completed / elapsed_total * 60 if elapsed_total > 0 else 0
                    eta = (total - completed - failed) / rate if rate > 0 else 0
                    log(f"[{completed}/{total}] {title} ✅ {result['entity_count']}E/{result['relation_count']}R "
                        f"({result.get('elapsed_s', 0):.0f}s) | {rate:.1f}篇/分 | 剩余:{eta:.0f}分")
            except Exception as e:
                failed += 1
                log(f"[{i+1}/{total}] {title} ❌ {type(e).__name__}: {e}")

    elapsed_total = time.time() - start_all
    log(f"\n{'='*50}")
    log(f"完成！成功: {completed}  失败: {failed}  总耗时: {elapsed_total/60:.1f} 分")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CeramiKG 陶瓷文献知识抽取 v3 (中文版)")
    parser.add_argument("results_dir", nargs="?", default="d:/CeramiKG/pdf-flask-handler/uploads/247",
                        help="论文结果目录")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS_PAPERS, help="并发论文数")
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE, help="分块大小（字符）")
    parser.add_argument("--force", action="store_true", help="强制重抽，覆盖已有的 extracted.json")
    args = parser.parse_args()

    print(f"🚀 CeramiKG 知识抽取 v3 (中文版)")
    print(f"   API: {BASE_URL}  模型: {MODEL}")
    print(f"   并发论文: {args.workers}  分块: {args.chunk_size}  块内并发: {MAX_WORKERS_PER_PAPER}")
    if args.force:
        print(f"   ⚠ --force: 全量重抽模式")

    # 启动前 API 连通检查
    print("🔍 检测 API 连通性...", end=" ", flush=True)
    test_raw = call_llm("Say 'OK' in one word, no other text.")
    if test_raw:
        print(f"✅ ({test_raw[:30]})")
    else:
        print("❌ API 连通失败！请检查网络/API_KEY/模型名称")
        sys.exit(1)

    batch_process(args.results_dir, workers=args.workers, chunk_size=args.chunk_size, force=args.force)
