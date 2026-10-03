"""端到端/单项验证驱动。用法: test_material_passport.py [phase]
  material  就地测试素材激化兑换(F→选产物→滚动翻页选材→Dry Run 取消),
            要求游戏已停在激化台前(交互提示可见), 不做导航不退出副本
  calendar  日历+朝夕心愿(礼物+任务领取)
  realm     完整素材激化链(导航进副本, Dry Run)
  passport  通行证(旅行任务一键领取+秘宝轨道)
  all       上面全部(默认), 从清理残留开始
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
    phase = sys.argv[1] if len(sys.argv) > 1 else 'all'
    print(f'PHASE: {phase}', flush=True)
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
    from src.tasks.CalendarTask import CalendarTask

    realm = RealmTask(executor=executor, app=ok.headless_app)
    realm.after_init(executor=executor, scene=executor.scene)
    realm.post_init()
    realm.config['Material Exchange Count'] = 1
    realm.config['Escalate Product'] = '噗灵'
    realm.config['Escalate Max'] = True
    realm.config['Dry Run'] = True  # 体力不足/单项验证, 只走到选择材料弹窗

    passport = PassportTask(executor=executor, app=ok.headless_app)
    passport.after_init(executor=executor, scene=executor.scene)
    passport.post_init()
    passport.config['Claim Passport Tasks'] = True
    passport.config['Claim Passport Rewards'] = True

    calendar = CalendarTask(executor=executor, app=ok.headless_app)
    calendar.after_init(executor=executor, scene=executor.scene)
    calendar.post_init()
    calendar.config['Claim Calendar Rewards'] = True
    calendar.config['Open Zhaoxi Quests'] = True

    def run_material_inplace():
        """就地兑换验证: 假定已在激化台前, 只走 F→选产物→选材(滚动翻页)→Dry Run 取消"""
        arm(180, 'material_inplace')
        try:
            boxes = realm.ocr(log=False)
            if not next((b for b in boxes if '激化台' in b.name), None):
                print('RESULT material_inplace: NOT at exchange table (no prompt), '
                      'use phase=realm for full nav', flush=True)
                return
            ok_ = realm.material_exchange_once(first=True)
            print(f'RESULT material_inplace done={ok_}', flush=True)
            print('RESULT realm infos:', json.dumps(realm.info, ensure_ascii=False, default=str),
                  flush=True)
        finally:
            disarm()

    if phase in ('all', 'material') and phase == 'material':
        run_material_inplace()
    else:
        if phase == 'all':
            # 清理残留(副本/奖励页)
            arm(240, 'cleanup')
            realm.ensure_foreground()
            realm.ensure_in_game()
            print('STEP cleanup: leave_material_dungeon ->',
                  realm.leave_material_dungeon(), flush=True)
            realm.back_to_world()
            disarm()

        if phase in ('all', 'calendar'):
            arm(300, 'calendar_task')
            try:
                calendar.run()
            finally:
                disarm()
            print('RESULT calendar infos:', json.dumps(calendar.info, ensure_ascii=False, default=str),
                  flush=True)

        if phase in ('all', 'realm'):
            MyBaseTask.zhaoxi_task_texts = ['很多新人搭配师不知道, 流转之柱开放了不少幻境, '
                                            '在素材激化幻境兑换1次素材 0/1 奖励 200']
            arm(420, 'realm_task')
            try:
                realm.run()
            finally:
                disarm()
            print('RESULT realm infos:', json.dumps(realm.info, ensure_ascii=False, default=str),
                  flush=True)

        if phase in ('all', 'passport'):
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
