import pandas as pd
import matplotlib.pyplot as plt
from itertools import cycle
import os
import numpy as np
import matplotlib.ticker as ticker  # 目盛りのフォーマット用

def plot_chunks(file_list):
    # None チェックを追加
    if not file_list:
        print("[INFO] No files provided to plot.")
        return

    # 単一ファイルパスが来たらリストに変換
    if isinstance(file_list, str):
        file_list = [file_list]

    print("[DEBUG] Plotting from files:")
    for f in file_list:
        print(f"  - {f}")

    dfs = []
    for file in file_list:
        if not os.path.isfile(file):
            print(f"[WARN] File not found: {file}")
            continue

        try:
            df = pd.read_csv(file)
            if all(col in df.columns for col in ["agent_id", "chunk_id", "time_pc_sec_abs", "a0", "a1", "a2"]):
                dfs.append(df[["agent_id", "chunk_id", "time_pc_sec_abs", "a0", "a1", "a2"]])
        except Exception as e:
            print(f"[WARN] Failed to load {file}: {e}")

    if not dfs:
        print("[INFO] No valid data to plot.")
        return

    df_all = pd.concat(dfs, ignore_index=True)
    fig, axs = plt.subplots(3, 1, figsize=(9, 6), sharex=True)
    colors = {}
    color_cycle = cycle(plt.rcParams['axes.prop_cycle'].by_key()['color'])

    for (ag_id, _), sub in df_all.groupby(["agent_id", "chunk_id"]):
        if ag_id not in colors:
            colors[ag_id] = next(color_cycle)
        axs[0].plot(sub["time_pc_sec_abs"], sub["a0"], color=colors[ag_id])
        axs[1].plot(sub["time_pc_sec_abs"], sub["a1"], color=colors[ag_id])
        axs[2].plot(sub["time_pc_sec_abs"], sub["a2"], color=colors[ag_id])

    axs[0].set_ylabel("a0")
    axs[1].set_ylabel("a1")
    axs[2].set_ylabel("a2")
    axs[2].set_xlabel("PC time (sec)")
    for ax in axs:
        ax.grid(True)

    handles = [plt.Line2D([0], [0], color=color, lw=2, label=f"Agent {ag_id}")
               for ag_id, color in colors.items()]
    axs[0].legend(handles=handles, title="Agents")

    plt.tight_layout()
    plt.show()

def correct_phase_discontinuity(phase_data):
    """
    位相データのジャンプを補正する関数。
    急激な変化があった場合に 256 を加算または減算して連続性を保つ。
    """
    corrected_phase = phase_data.copy()
    for i in range(1, len(corrected_phase)):
        diff = corrected_phase[i] - corrected_phase[i - 1]
        if diff < -128:  # 急に128以上小さくなった場合
            corrected_phase[i:] += 256
        elif diff > 128:  # 急に128以上大きくなった場合
            corrected_phase[i:] -= 256
    return corrected_phase

def plot_relativePhase(file_list):
    # None チェックを追加
    if not file_list:
        print("[INFO] No files provided to plot.")
        return

    # 単一ファイルパスが来たらリストに変換
    if isinstance(file_list, str):
        file_list = [file_list]

    print("[DEBUG] Plotting from files:")
    for f in file_list:
        print(f"  - {f}")

    dfs = []
    for file in file_list:
        if not os.path.isfile(file):
            print(f"[WARN] File not found: {file}")
            continue

        try:
            df = pd.read_csv(file)
            if all(col in df.columns for col in ["agent_id", "chunk_id", "time_pc_sec_abs", "a0", "a1", "a2"]):
                dfs.append(df[["agent_id", "chunk_id", "time_pc_sec_abs", "a0", "a1", "a2"]])
        except Exception as e:
            print(f"[WARN] Failed to load {file}: {e}")

    if not dfs:
        print("[INFO] No valid data to plot.")
        return

    df_all = pd.concat(dfs, ignore_index=True)

    # 新しい時系列を定義 (100Hz)
    min_time = df_all["time_pc_sec_abs"].min()
    max_time = df_all["time_pc_sec_abs"].max()

    for agent_id, sub in df_all.groupby("agent_id"):
        sub = sub.sort_values("time_pc_sec_abs")
        min_time = max(min_time, sub["time_pc_sec_abs"].min())
        max_time = min(max_time, sub["time_pc_sec_abs"].max())

    if min_time >= max_time:
        print(f"[INFO] No overlapping time range for agents. min_time={min_time}, max_time={max_time}")
        return

    new_time_series = np.arange(min_time, max_time, 0.01) - min_time  # 最小値を基準にシフト

    # 線形補間で位相データを再定義
    interpolated_data = {}
    for agent_id, sub in df_all.groupby("agent_id"):
        sub = sub.sort_values("time_pc_sec_abs")
        sub["a0"] = correct_phase_discontinuity(sub["a0"].values)
        interpolated_data[agent_id] = {
            "time": new_time_series,
            "a0": np.interp(new_time_series + min_time, sub["time_pc_sec_abs"], sub["a0"])  # シフト前の時間で補間
        }

    # 基準エージェントの選択
    base_agent_id = min(interpolated_data.keys())
    base_agent_a0 = interpolated_data[base_agent_id]["a0"]

    fig, ax = plt.subplots(figsize=(9, 6))
    colors = cycle(plt.rcParams['axes.prop_cycle'].by_key()['color'])

    # 線形補間と補正後のデータを使用して相対位相差を計算
    for agent_id, data in interpolated_data.items():
        if agent_id == base_agent_id:
            continue

        phase_diff = (data["a0"] - base_agent_a0 + 128) % 256 - 128
        phase_diff_with_nan = phase_diff.copy()
        for i in range(1, len(phase_diff)):
            if abs(phase_diff[i] - phase_diff[i - 1]) > 128:
                phase_diff_with_nan[i] = np.nan

        # 縦軸のデータを 2π/256 でスケール
        phase_diff_with_nan = phase_diff_with_nan * (2 * np.pi / 256)

        print(f"[DEBUG] Agent {agent_id}: Phase diff with NaN (first 10 values) = {phase_diff_with_nan[:10]}")
        ax.plot(data["time"], phase_diff_with_nan, label=f"Agent {agent_id} - Agent {base_agent_id}", color=next(colors))

    # 縦軸の目盛りをπ単位で設定し、範囲を -π から π に制限
    ax.set_ylim(-np.pi, np.pi)
    ax.yaxis.set_major_locator(ticker.MultipleLocator(base=np.pi / 2))  # π/2 間隔
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x / np.pi)}π" if x % np.pi == 0 else f"{x / np.pi:.1f}π"))

    # プロットの設定
    ax.set_ylabel("Phase Diff (radians)")
    ax.set_xlabel("Time (s)")
    ax.legend(title="Relative Phase")
    ax.grid(True)

    # 横軸の範囲をデータの両端に合わせる
    ax.set_xlim(0, new_time_series[-1])

    plt.tight_layout()
    plt.show()
