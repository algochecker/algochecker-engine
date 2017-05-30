from collections import namedtuple

Package = namedtuple('Package', ['file_name', 'path', 'raw_config', 'config'])

TestUnit = namedtuple('TestUnit', ['name', 'runner_meta'])

CompileStatus = namedtuple('CompileStatus', ['status', 'message'])
CompileStatus.__new__.__defaults__ = (None,)

ExecStatus = namedtuple('ExecStatus', ['status', 'timeout', 'exit_code', 'exec_time', 'memory'])
ExecStatus.__new__.__defaults__ = (None, None, None)

EvalStatus = namedtuple('EvalStatus', ['status', 'awarded_points', 'max_points'])

TestStatus = namedtuple('TestStatus', ['name', 'status', 'time', 'timeout',
                                       'memory', 'points', 'max_points'])
TestStatus.__new__.__defaults__ = (None, None, None, None, None)

FinalResult = namedtuple('FinalResult', ['status', 'uuid', 'checked_by', 'score', 'message', 'tests', 'time_stats'])
FinalResult.__new__.__defaults__ = (None, 0, None, [], None)
