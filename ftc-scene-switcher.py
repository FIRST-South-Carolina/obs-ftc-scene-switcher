import obspython as obs

import asyncio
import json
import queue
import threading
import time

import websockets


settings = None
hotkeys = {}
thread = None

comm = None
stop = None
lock = None

reconnect_tries = 0
post_time = -1


msg_mapping = {
    'MATCH_LOAD': 'match_load',
    'MATCH_START': 'match_start',
    'MATCH_ABORT': 'match_abort',
    'MATCH_COMMIT': 'match_commit',
    'MATCH_POST': 'match_post',
    # state for an alternative scene between matches - not sent by scorekeeper
    'MATCH_WAIT': 'match_wait',
}


def script_description():
    return '<b>FTC Scene Switcher</b><hr/>Switch scenes based on events from the FTCLive scorekeeping software.<br/><br/>Made by Lily Foster &lt;lily@lily.flowers&gt;'


def script_load(settings_):
    global settings, comm, stop, lock

    settings = settings_

    # cross-thread communication
    comm = queue.Queue(32)
    stop = threading.Event()
    lock = threading.Lock()

    # OBS thread communication checker
    obs.timer_add(check_websocket, 100)

    # get saved hotkey data
    hotkey_enable = obs.obs_data_get_array(settings, 'hotkey_enable')
    hotkey_disable = obs.obs_data_get_array(settings, 'hotkey_disable')

    # register hotkeys
    hotkeys['enable'] = obs.obs_hotkey_register_frontend('ftc-scene-switcher_enable', '(FTC) Enable automatic scene switcher', enable)
    hotkeys['disable'] = obs.obs_hotkey_register_frontend('ftc-scene-switcher_disable', '(FTC) Disable automatic scene switcher', disable)

    # load saved hotkey data
    obs.obs_hotkey_load(hotkeys['enable'], hotkey_enable)
    obs.obs_hotkey_load(hotkeys['disable'], hotkey_disable)

    # release data references
    obs.obs_data_array_release(hotkey_enable)
    obs.obs_data_array_release(hotkey_disable)


def script_unload():
    global thread

    # stop websocket thread
    if thread and thread.is_alive():
        stop.set()
        thread.join()

        thread = None

    # stop communication checker
    obs.timer_remove(check_websocket)


def script_save(settings):
    # save hotkey data
    hotkey_enable = obs.obs_hotkey_save(hotkeys['enable'])
    hotkey_disable = obs.obs_hotkey_save(hotkeys['disable'])

    # set hotkey data
    obs.obs_data_set_array(settings, 'hotkey_enable', hotkey_enable)
    obs.obs_data_set_array(settings, 'hotkey_disable', hotkey_disable)

    # release data references
    obs.obs_data_array_release(hotkey_enable)
    obs.obs_data_array_release(hotkey_disable)


def script_properties():
    props = obs.obs_properties_create()

    general_props = obs.obs_properties_create()
    obs.obs_properties_add_group(props, 'general', 'General', obs.OBS_GROUP_NORMAL, general_props)

    obs.obs_properties_add_bool(general_props, 'enabled', 'Enabled')
    obs.obs_properties_add_bool(general_props, 'override_non_match_scenes', 'Override Non-Match Scenes')
    obs.obs_properties_add_text(general_props, 'scorekeeper_ws', 'Scorekeeper WS', obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_int(general_props, 'match_wait_time', 'Match Post Time to Match Wait', -1, 600, 1)

    scene_props = obs.obs_properties_create()
    obs.obs_properties_add_group(props, 'scene', 'Scenes', obs.OBS_GROUP_NORMAL, scene_props)

    obs.obs_properties_add_text(scene_props, 'match_load', 'Match Load', obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_text(scene_props, 'match_start', 'Match Start', obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_text(scene_props, 'match_abort', 'Match Abort', obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_text(scene_props, 'match_commit', 'Match Commit', obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_text(scene_props, 'match_post', 'Match Post', obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_text(scene_props, 'match_wait', 'Match Wait', obs.OBS_TEXT_DEFAULT)

    return props


def script_defaults(settings):
    obs.obs_data_set_default_bool(settings, 'enabled', True)
    obs.obs_data_set_default_bool(settings, 'override_non_match_scenes', False)
    obs.obs_data_set_default_string(settings, 'scorekeeper_ws', 'ws://localhost/api/v2/stream/')
    obs.obs_data_set_default_int(settings, 'match_wait_time', 30)

    obs.obs_data_set_default_string(settings, 'match_load', 'Match Load')
    obs.obs_data_set_default_string(settings, 'match_start', 'Match Start')
    obs.obs_data_set_default_string(settings, 'match_abort', 'Match Abort')
    obs.obs_data_set_default_string(settings, 'match_commit', 'Match Commit')
    obs.obs_data_set_default_string(settings, 'match_post', 'Match Post')
    obs.obs_data_set_default_string(settings, 'match_wait', 'Match Wait')


def script_update(settings):
    global thread

    if thread and thread.is_alive():
        print(f'Disconnecting from scorekeeper WS')

        stop.set()
        thread.join()

        thread = None

    if not obs.obs_data_get_bool(settings, 'enabled'):
        return

    print(f'Connecting to scorekeeper WS')

    # TODO: change to asyncio.run when OBS is at Py3.7+ on Windows
    thread = threading.Thread(target=lambda: asyncio.get_event_loop().run_until_complete(run_websocket(obs.obs_data_get_string(settings, 'scorekeeper_ws'))))
    thread.start()


def enable(pressed=False):
    if pressed:
        return

    obs.obs_data_set_bool(settings, 'enabled', True)

    script_update()


def disable(pressed=False):
    if pressed:
        return

    obs.obs_data_set_bool(settings, 'enabled', False)

    script_update()


def check_websocket():
    global thread, reconnect_tries, post_time

    if not obs.obs_data_get_bool(settings, 'enabled'):
        return

    if thread and not thread.is_alive():
        # thread died and needs to be retried or cleaned up
        print(f'ERROR: Connection to scorekeeper WS failed')
        print()

        # lock for reconnect_tries
        with lock:
            if reconnect_tries < 10:
                # retry a few times by running the script reload callback
                reconnect_tries += 1
            else:
                # just give up and manually cleanup thread
                thread = None

        if thread:
            # in a different conditional so lock can be released
            print(f'Retrying connection...')
            script_update()

        # no return to let queue continue to be cleared since we are enabled

    try:
        while True:
            if obs.obs_source_get_name(obs.obs_frontend_get_current_scene()) == obs.obs_data_get_string(settings, 'match_post') and obs.obs_data_get_int(settings, 'match_wait_time') >= 0 and post_time >= 0 and time.time() >= post_time + obs.obs_data_get_int(settings, 'match_wait_time'):
                # still in match post scene and timer has been reached - set to match wait
                scene = 'match_wait'
                post_time = -1
            else:
                # check websocket for events
                msg = comm.get_nowait()
                scene = msg_mapping[msg['updateType']]

            # bail if not currently on a recognized scene
            if not obs.obs_data_get_bool(settings, 'override_non_match_scenes') and obs.obs_source_get_name(obs.obs_frontend_get_current_scene()) not in map(lambda scene: obs.obs_data_get_string(settings, scene), msg_mapping.values()):
                continue

            # find and set the current scene based on websocket or wait set above
            sources = obs.obs_enum_sources()
            for source in sources:
                if obs.obs_source_get_type(source) == obs.OBS_SOURCE_TYPE_SCENE and obs.obs_source_get_name(source) == obs.obs_data_get_string(settings, scene):
                    obs.obs_frontend_set_current_scene(source)
                    break
            obs.source_list_release(sources)

            # record when a scene was switched to match post
            if scene == 'match_post':
                post_time = time.time()
    except queue.Empty:
        pass


async def run_websocket(uri):
    global reconnect_tries

    async with websockets.connect(uri) as websocket:
        with lock:
            reconnect_tries = 0

        # thread kill-switch check
        while not stop.is_set():
            try:
                # try to get something from websocket and put it in queue for main thread (dropping events when queue is full)
                comm.put_nowait(json.loads(await asyncio.wait_for(websocket.recv(), 0.2)))
            except (asyncio.TimeoutError, queue.Full):
                pass
