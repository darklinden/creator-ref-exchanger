#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import shutil
import subprocess
import sys


class Logger:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'

    def head(self, s):
        print(self.HEADER + str(s) + self.ENDC)

    def blue(self, s):
        print(self.OKBLUE + str(s) + self.ENDC)

    def green(self, s):
        print(self.OKGREEN + str(s) + self.ENDC)

    def warn(self, s):
        print(self.WARNING + str(s) + self.ENDC)

    def fail(self, s):
        print(self.FAIL + str(s) + self.ENDC)


log = Logger()


def run_cmd(cmd):
    log.blue("run cmd: " + " ".join(cmd))
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if err:
        print(err)
    return out


def self_install(file, des):
    file_path = os.path.realpath(file)

    filename = file_path

    pos = filename.rfind("/")
    if pos:
        filename = filename[pos + 1:]

    pos = filename.find(".")
    if pos:
        filename = filename[:pos]

    to_path = os.path.join(des, filename)

    log.blue("installing [" + file_path + "] \n\tto [" + to_path + "]")
    if os.path.isfile(to_path):
        os.remove(to_path)

    shutil.copy(file_path, to_path)
    run_cmd(['chmod', 'a+x', to_path])


def base_folder(path):
    path = os.path.normpath(path)
    path = str(path).rstrip(os.path.sep)
    pos = path.rfind(os.path.sep)
    if pos == -1:
        return ""
    else:
        path = path[:pos]
        path = path.rstrip(os.path.sep)
        return path


def dict_get_uuids(dict_data: dict) -> dict:
    uuid_data = None
    for key in dict_data.keys():
        o = dict_data[key]
        if str(key).lower().find('uuid') != -1:
            if uuid_data is None:
                uuid_data = {}
            uuid_data[key] = o
        else:
            if isinstance(o, dict):
                o = dict_get_uuids(o)
                if o is not None:
                    if uuid_data is None:
                        uuid_data = {}
                    uuid_data[key] = o
            elif isinstance(o, list):
                log.warn('meta data contains list')
    return uuid_data


# return map :
# '01.png' : <
# 'name': '01.png',
# 'des': {
#  ..: .. : {uuid :
# }
# >
def list_destination_references(folder_to):
    log.head('list destination references ...')

    ret = {}
    # find all fnt
    for root, dirs, files in os.walk(folder_to):
        for f in files:
            if not f.lower().endswith('.meta'):
                continue

            meta_file_path = os.path.join(root, f)
            file_path = meta_file_path[:-5]

            if os.path.isdir(file_path):
                continue

            relative_file_path = file_path[(len(folder_to) + 1):]

            j = json.load(open(meta_file_path))
            ref = {}
            ref['name'] = relative_file_path
            ref['des'] = dict_get_uuids(j)
            ret[relative_file_path] = ref

    return ret


def name_similar(path1, path2):
    num = 0

    if os.path.basename(path1) == os.path.basename(path2):
        for x in range(1, min(len(path1), len(path2))):
            if path1[-x] == path2[-x]:
                num += 1
            else:
                break

    return num


def match_uuid_dict(f_data, t_data, comment):
    uuid_data = []

    for key in f_data.keys():
        o_f = f_data.get(key, None)
        o_t = t_data.get(key, None)

        if isinstance(o_f, str) and isinstance(o_t, str):
            uuid_data.append({
                "comment": comment,
                "f": o_f,
                "t": o_t
            })
        elif isinstance(o_f, dict) and isinstance(o_t, dict):
            uuid_data += match_uuid_dict(o_f, o_t, comment)
        else:
            log.warn(str(o_f) + ' compare ' + str(o_t) + ' not match')

    return uuid_data


# return map :
# [{
# 'f':'',
# 't':''
# }]
def match_source_references(folder_from, des_refers):
    log.head('match source references ...')
    warn = 0
    ref = 0
    yes_to_all = False
    matches = []

    # fill refers
    for root, dirs, files in os.walk(folder_from):
        for f in files:
            if not f.lower().endswith('.meta'):
                continue

            meta_file_path = os.path.join(root, f)
            file_path = meta_file_path[:-5]

            if os.path.isdir(file_path):
                continue

            relative_file_path = file_path[(len(folder_from) + 1):]

            in_ref_list = False
            ref_key = ''
            for rk in des_refers:
                n = des_refers[rk]
                if name_similar(file_path, n['name']) >= 5:
                    ref_key = rk
                    in_ref_list = True
                    break

            if not in_ref_list:
                log.warn(f + ' in [ ' + root + ' ] not in ref list')
                print()
                warn += 1
                continue

            j = json.load(open(meta_file_path))
            uuid_data = dict_get_uuids(j)
            log.head('will replace ref [ ' + file_path + ' ] with [ ' + des_refers[ref_key]['name'] + ' ]')

            do = None
            if not yes_to_all:
                log.fail('return to continue, n/N to skip, A yes to all')
                do = input()

            if do is not None and do.strip().startswith('A'):
                yes_to_all = True

            if yes_to_all or (not do.strip().startswith('n')):
                matches += match_uuid_dict(uuid_data, des_refers[ref_key]['des'], relative_file_path)

            ref += 1

    return matches, warn, ref


def contains_src_uuid(matched_refers, line):
    uuid = []
    for o in matched_refers:
        if len(o['f']) > 0 and str(line).find(o['f']) != -1:
            uuid.append(o)
    return uuid


def exchange_references(matched_refers, project_path):
    assets = os.path.join(project_path, 'assets')

    for root, dirs, files in os.walk(assets):
        for fn in files:
            if not (fn.lower().endswith('.anim') or fn.lower().endswith('.prefab') or fn.lower().endswith('.fire')):
                continue

            file_path = os.path.join(root, fn)

            log.head('working on ' + file_path + ' ...')

            f = open(file_path)
            content = f.readlines()
            f.close()

            for i in range(0, len(content)):
                l = content[i]
                matched_list = contains_src_uuid(matched_refers, l)
                if len(matched_list) == 0:
                    continue

                start = i - 2
                if start < 0:
                    start = 0
                end = i + 3
                if end > len(content):
                    end = len(content)

                log.head('found lines to replace: ' + str(i))

                for j in range(start, end):
                    s = content[j]
                    s = s.strip('\n')
                    log.blue(s)

                for o in matched_list:
                    log.head('replace ref [' + o['f'] + '] to [' + o['t'] + '] of ' + o['comment'])

                    content[i] = content[i].replace(o['f'], o['t'])

            f = open(file_path, 'w')
            f.writelines(content)
            f.close()


def deal_with_references(folder_from, folder_to, project_path):
    des_refers = list_destination_references(folder_to)

    log.head('get des references:')
    for k in des_refers.keys():
        log.blue(k)

    print()

    print()

    matches, warn_count, ref_count = match_source_references(folder_from, des_refers)

    for o in matches:
        log.green('will exchange ref ' + o['comment'] + ':')
        log.blue('\t' + o['f'] + '  -  ' + o['t'])

        print()

    log.fail('warn count: ' + str(warn_count))
    log.fail('ref count: ' + str(ref_count))
    log.fail('continue? Y/n')

    do = input()

    if do.strip().startswith('Y'):
        exchange_references(matches, project_path)


def main():
    # self_install
    if len(sys.argv) > 1 and sys.argv[1] == 'install':
        self_install("creator-reference-exchanger.py", "/usr/local/bin")
        return

    arg_len = len(sys.argv)

    folder_from = ""
    folder_to = ""
    project_path = ""

    idx = 1
    while idx < arg_len:
        cmd_s = sys.argv[idx]
        if cmd_s[0] == "-":
            c = cmd_s[1:]
            v = sys.argv[idx + 1]
            if c == "f":
                folder_from = v
            elif c == "t":
                folder_to = v
            elif c == "p":
                project_path = v
            idx += 2
        else:
            idx += 1

    if len(folder_from) == 0 or len(folder_to) == 0:
        print('using creator-reference-exchanger '
              '\n\t-f [from folder path]'
              '\n\t-t [to folder path]'
              '\n\t-p [project path]'
              "\n\tto run")
        return

    if not os.path.isabs(folder_from):
        folder_from = os.path.join(os.getcwd(), folder_from)

    if not os.path.isabs(folder_to):
        folder_to = os.path.join(os.getcwd(), folder_to)

    if not os.path.isabs(project_path):
        if project_path == '.':
            project_path = os.getcwd()
        else:
            project_path = os.path.join(os.getcwd(), project_path)

    deal_with_references(folder_from, folder_to, project_path)

    log.green('Done.')


if __name__ == '__main__':
    main()
