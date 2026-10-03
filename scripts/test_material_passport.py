"""端到端验证: RealmTask 素材激化幻境兑换 + PassportTask 旅行任务/轨道领取。
- 先清理当前副本内残留状态(leave_material_dungeon)
- 模拟朝夕心愿任务文本路由到素材激化幻境, 真实兑换 1 次(1 单位材料 ≈ 10 体力)
- PassportTask: 旅行任务领取(当前无可领则为 0)+ 秘宝页一键领取
"""
import json
import os
import sys
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ok import OK, og

from src.config import config

WATCH = {'deadline': 0.0, 'name': ''}


def watchdog():
    while True:
        time.sleep(5)
        if WATCH['deadline'] and time.time() > WATCH['deadline']:
            print(f'WATCHDOG timeout: {WATCH["name"]}', flush=True)
            os._exit(2)


def arm(seconds, name):
    WATCH['deadline'] = time.time() + seconds
    WATCH['name'] = name


def disarm():
    WATCH['deadline'] = 0.0


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    threading.Thread(target=watchdog, daemon=True).start()

    c = dict(config)
    c.pop('gui', None)
    c['use_gui'] = False
    c['onetime_tasks'] = []
    ok = OK(c)
    dm = ok.device_manager
    dm.do_refresh(True)
    if dm.get_preferred_device() is None:
        dm.set_preferred_device()
    dm.do_start()
    executor = ok.task_executor
    executor.start()
    og.app = ok

    from src.tasks.MyBaseTask import MyBaseTask
    from src.tasks.RealmTask import RealmTask
    from src.tasks.PassportTask import PassportTask

    realm = RealmTask(executor=executor, app=ok.headless_app)
    realm.after_init(executor=executor, scene=executor.scene)
    realm.post_init()
    realm.config['Material Exchange Count'] = 1
    realm.config['Escalate Product'] = '噗灵'
    realm.config['Escalate Max'] = True
    realm.config['Dry Run'] = False

    passport = PassportTask(executor=executor, app=ok.headless_app)
    passport.after_init(executor=executor, scene=executor.scene)
    passport.post_init()
    passport.config['Claim Passport Tasks'] = True
    passport.config['Claim Passport Rewards'] = True

    # 1) 清理: 上次可能残留在副本/奖励页
    arm(240, 'cleanup')
    realm.ensure_foreground()
    realm.ensure_in_game()
    print('STEP cleanup: leave_material_dungeon ->',
          realm.leave_material_dungeon(), flush=True)
    realm.back_to_world()
    disarm()

    # 2) RealmTask: 模拟朝夕心愿任务路由到素材激化
    MyBaseTask.zhaoxi_task_texts = ['很多新人搭配师不知道, 流转之柱开放了不少幻境, '
                                    '在素材激化幻境兑换1次素材 0/1 奖励 200']
    arm(420, 'realm_task')
    try:
        realm.run()
    finally:
        disarm()
    print('RESULT realm infos:', json.dumps(realm.info, ensure_ascii=False, default=str),
          flush=True)

    # 3) PassportTask
    arm(240, 'passport_task')
    try:
        passport.run()
    finally:
        disarm()
    print('RESULT passport infos:', json.dumps(passport.info, ensure_ascii=False, default=str),
          flush=True)

    print('SESSION DONE', flush=True)
    time.sleep(1)
    os._exit(0)


if __name__ == '__main__':
    main()
