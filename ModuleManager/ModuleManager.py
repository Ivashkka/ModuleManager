from queue import Queue
from threading import Thread, Event
from abc import ABC, abstractmethod
from typing import Any, Callable
from pydantic import PositiveInt, BaseModel, Field


class MyModuleConf(BaseModel):
    instances_count : int = Field(default=0)
    stdin : bool = Field(default=True)
    stdout : bool = Field(default=True)

class MyModuleState(BaseModel):
    started : bool = Field(default=False)
    paused : bool = Field(default=False)
    idle : bool = Field(default=True)
    has_error : bool = Field(default=False)

class MyModuleInput(BaseModel):
    pass

class MyModuleOutput(BaseModel):
    pass




class BaseMyModuleInstance(ABC):
    __slots__ = ['_stop_event', '_pause_event', '_main_thread', '_stdin', '_stdout', '_stderr', 'id', 'conf', 'state']

    @abstractmethod
    def my_conf_holder() -> type[MyModuleConf]: return MyModuleConf

    @abstractmethod
    def my_state_holder() -> type[MyModuleState]: return MyModuleState

    @abstractmethod
    def my_input_holder() -> type[MyModuleInput]: return MyModuleInput

    @abstractmethod
    def my_output_holder() -> type[MyModuleOutput]: return MyModuleOutput

    @abstractmethod
    def post_init(self) -> None: pass

    @abstractmethod
    def post_term(self) -> None: pass

    @abstractmethod
    def __init__(self, stdin : Queue, stdout : Queue, stderr : Queue, id : int): pass

    @abstractmethod
    def term(self): pass

    @abstractmethod
    def _main_thread_body(self): pass

    @abstractmethod
    def wait_if_paused(self): pass

    @abstractmethod
    def pause(self): pass

    @abstractmethod
    def unpause(self): pass

    @abstractmethod
    def get(self, wait : bool = False) -> MyModuleOutput | None: pass

    @abstractmethod
    def empty_output(self) -> bool: pass

    @abstractmethod
    def put(self, inputdata : MyModuleInput): pass

    @abstractmethod
    def check(self) -> Exception | None: pass

    @abstractmethod
    def _take(self) -> MyModuleInput | None: pass

    @abstractmethod
    def _give(self, outputdata : MyModuleOutput): pass

    @abstractmethod
    def i_handled_error(self): pass

    @abstractmethod
    def main_thread_iteration(self, stdin : MyModuleInput) -> MyModuleOutput: return None

    @abstractmethod
    def main_thread_iteration_condition(self) -> bool: return True



class RootMyModule(ABC):
    _main_thread : Thread = None
    _stop_event : Event = None

    _input_type : type[MyModuleInput] = None
    _output_type : type[MyModuleOutput] = None

    _stdin : Queue = None
    _stdout : Queue = None

    @abstractmethod
    def init(): pass

    @abstractmethod
    def term(): pass

    @abstractmethod
    def _main_thread_body(): pass

    @abstractmethod
    def get(wait : bool = False) -> MyModuleOutput | None: pass

    @abstractmethod
    def empty_output() -> bool: pass

    @abstractmethod
    def put(inputdata : MyModuleInput): pass

    @abstractmethod
    def _take() -> MyModuleInput | None: pass

    @abstractmethod
    def _give(outputdata : MyModuleOutput): pass




class BaseMyModule(RootMyModule):
    _pause_event : Event = None

    _instance_type : type[BaseMyModuleInstance] = None

    conf : MyModuleConf = None
    state : MyModuleState = None

    _instances : list[BaseMyModuleInstance] = None

    _stderr : Queue = None

    _instances_in : Queue = None
    _instances_out : Queue = None
    _instances_err : Queue = None

    @abstractmethod
    def post_init() -> None: pass

    @abstractmethod
    def post_term() -> None: pass

    @abstractmethod
    def init_condition() -> bool : return True

    @abstractmethod
    def my_conf_holder() -> type[MyModuleConf]: return MyModuleConf

    @abstractmethod
    def my_state_holder() -> type[MyModuleState]: return MyModuleState

    @abstractmethod
    def my_input_holder() -> type[MyModuleInput]: return MyModuleInput

    @abstractmethod
    def my_output_holder() -> type[MyModuleOutput]: return MyModuleOutput

    @abstractmethod
    def my_instance_holder() -> type[BaseMyModuleInstance]: return BaseMyModuleInstance

    @abstractmethod
    def wait_if_paused(): pass

    @abstractmethod
    def pause(): pass

    @abstractmethod
    def unpause(): pass

    @abstractmethod
    def check() -> Exception | None: pass

    @abstractmethod
    def _take_inst() -> MyModuleOutput | None: pass

    @abstractmethod
    def _give_inst(inputdata : MyModuleInput): pass

    @abstractmethod
    def i_handled_error(): pass

    @abstractmethod
    def main_thread_iteration(stdin : MyModuleInput | MyModuleOutput) -> MyModuleOutput | MyModuleInput: return None

    @abstractmethod
    def main_thread_iteration_condition() -> bool: return True

    @abstractmethod
    def _reset_module(): pass

class MyModuleInstance(BaseMyModuleInstance):
    __slots__ = ['_stop_event', '_pause_event', '_main_thread', '_stdin', '_stdout', '_stderr', 'id', 'conf', 'state']

    def __init__(self, stdin : Queue, stdout : Queue, stderr : Queue, id : int):
        self.conf = self.__class__.my_conf_holder()()
        self.state = self.__class__.my_state_holder()()
        self._input_type = self.__class__.my_input_holder()
        self._output_type = self.__class__.my_output_holder()
        self._stop_event = Event()
        self._pause_event = Event()
        self._stdin = stdin if self.conf.stdin else None
        self._stdout = stdout if self.conf.stdout else None
        self._stderr = stderr
        self.id = id
        self._main_thread = Thread(target=self._main_thread_body, name=self.__class__.__name__+f" id:{self.id} main thread", args=[])
        self._main_thread.start()
        self.state.started = True

    def term(self):
        self._stop_event.set()
        self._main_thread.join()
        self.post_term()

    def _main_thread_body(self):
        self.post_init()
        idle_count = 2
        while not self._stop_event.is_set():
            try:
                if idle_count < 2: idle_count += 1
                if not self._stderr.empty(): self.state.has_error = True
                if self._main_iteration_able_to_perform():
                    idle_count = 0
                    self.state.idle = False
                    if self.conf.stdin:
                        inputdata = self._take()
                        if inputdata == None: raise Exception(f'{self.__class__.__name__} internal error. None input')
                        outputdata = self.main_thread_iteration(inputdata)
                    else:
                        outputdata = self.main_thread_iteration()
                    if self.conf.stdout:
                        self._give(outputdata)
                if idle_count >= 2: self.state.idle = True
                self.wait_if_paused()
            except Exception as err:
                idle_count = 2
                self.state.idle = True
                self.state.has_error = True
                self._stderr.put(err)
                self.pause()

    def _main_iteration_able_to_perform(self) -> bool:
        if not self.conf.stdin: return self.main_thread_iteration_condition()
        else: return (not self._stdin.empty()) and self.main_thread_iteration_condition()

    def wait_if_paused(self):
       while self._pause_event.is_set():
            if self._stop_event.is_set():
                self.unpause()

    def pause(self):
        self._pause_event.set()
        self.state.paused = True

    def unpause(self):
        if self.state.has_error:
            raise Exception(f'{self.__class__.__name__} has errors in stderr queue. Handle them before unpausing')
        self._pause_event.clear()
        self.state.paused = False

    def get(self, wait : bool = False) -> MyModuleOutput | None:
        if not self.conf.stdout: raise Exception(f'{self.__class__.__name__} has no stdout queue')
        if (not wait) and self._stdout.empty(): return None
        outputdata = self._stdout.get()
        if type(outputdata) != self._output_type: raise ValueError(f'{self.__class__.__name__} gave bad output data type. Must be: {self._output_type}')
        return outputdata

    def empty_output(self) -> bool:
        return self._stdout.empty()

    def put(self, inputdata : MyModuleInput):
        if not self.conf.stdin: raise Exception(f'{self.__class__.__name__} has no stdin queue')
        if type(inputdata) != self._input_type: raise ValueError(f'bad input data type. {self.__class__.__name__} wants: {self._input_type}')
        self._stdin.put(inputdata)

    def check(self) -> Exception | None:
        if self._stderr.empty(): return None
        return self._stderr.get()

    def _take(self) -> MyModuleInput | None:
        if not self.conf.stdin: raise Exception(f'{self.__class__.__name__} internal stdin error (no stdin queue)')
        if self._stdin.empty(): return None
        inputdata = self._stdin.get()
        if type(inputdata) != self._input_type: raise ValueError(f'{self.__class__.__name__} internal stdin error (wrong type)')
        return inputdata

    def _give(self, outputdata : MyModuleOutput):
        if not self.conf.stdout: raise Exception(f'{self.__class__.__name__} internal stdout error (no stdout queue)')
        if type(outputdata) != self._output_type: raise ValueError(f'{self.__class__.__name__} internal stdout error (wrong type)')
        self._stdout.put(outputdata)

    def i_handled_error(self):
        if not self._stderr.empty(): raise Exception(f'{self.__class__.__name__} has more errors in stderr queue')
        self.state.has_error = False
        self.unpause()





class MyModule(BaseMyModule):
    @classmethod
    def init(cls):
        if cls.state != None: raise Exception(f'looks like {cls.__name__} has been stopped incorrectly. Failed to start')
        if not cls.init_condition(): raise Exception(f'{cls.__name__} failed to pass init condition. Failed to start')
        cls.conf = cls.my_conf_holder()()
        cls.state = cls.my_state_holder()()
        cls._input_type = cls.my_input_holder()
        cls._output_type = cls.my_output_holder()
        cls._instance_type = cls.my_instance_holder()
        cls._stop_event = Event()
        cls._pause_event = Event()
        cls._stdin = Queue() if cls.conf.stdin else None
        cls._stdout = Queue() if cls.conf.stdout else None
        cls._stderr = Queue()
        cls._instances = []
        if cls.conf.instances_count > 0:
            cls._instances_in = Queue()
            cls._instances_out = Queue()
            cls._instances_err = Queue()
            for i in range(0, cls.conf.instances_count):
                cls._instances.append(cls._instance_type(cls._instances_in, cls._instances_out, cls._instances_err, i))
        cls._main_thread = Thread(target=cls._main_thread_body, name=cls.__name__+" main thread", args=[])
        cls._main_thread.start()
        cls.state.started = True

    @classmethod
    def term(cls) -> bool:
        if (cls.state == None or cls.state.started == False):
            raise Exception(f'looks like {cls.__name__} has been started incorrectly. Failed to stop')
        for i in cls._instances:
            i.term()
        cls._stop_event.set()
        cls._main_thread.join()
        cls.post_term()
        cls._reset_module()

    @classmethod
    def _reset_module(cls):
        cls._main_thread = None
        cls._stop_event = None
        cls._pause_event = None
        cls._input_type = None
        cls._output_type = None
        cls._instance_type = None
        cls.conf = None
        cls.state = None
        cls._stdin = None
        cls._stdout = None
        cls._stderr = None
        cls._instances = None
        cls._instances_in = None
        cls._instances_out = None
        cls._instances_err = None

    @classmethod
    def _main_thread_body(cls):
        cls.post_init()
        idle_count = 2
        while not cls._stop_event.is_set():
            try:
                if idle_count < 2: idle_count += 1
                if not cls._stderr.empty(): cls.state.has_error = True
                for i in cls._instances:
                    inst_err = i.check()
                    if inst_err != None:
                        raise Exception(f'{cls.__name__} internal error (instance with id {i.id} got error {inst_err})')
                if cls._main_iteration_able_to_perform():
                    idle_count = 0
                    cls.state.idle = False
                    cls._pipe()
                if idle_count >= 2: cls.state.idle = True
                cls.wait_if_paused()
            except Exception as err:
                idle_count = 2
                cls.state.idle = True
                cls.state.has_error = True
                cls._stderr.put(err)
                cls.pause()

    @classmethod
    def _main_iteration_able_to_perform(cls) -> bool:
        if not cls.main_thread_iteration_condition(): return False
        if not cls._instances_out.empty(): return True
        if not cls.conf.stdin: return True
        else: return not cls._stdin.empty()

    @classmethod
    def _pipe(cls):
        inputdata = None
        outputdata = None
        if cls.conf.stdin:
            inputdata = cls._take()
        if inputdata == None and cls.conf.instances_count > 0:
            inputdata = cls._take_inst()
        if cls.conf.stdin and inputdata != None:
            outputdata = cls.main_thread_iteration(inputdata)
        elif cls.conf.instances_count > 0 and inputdata != None:
            outputdata = cls.main_thread_iteration(inputdata)
        else: raise Exception(f'{cls.__name__} internal error (None pipe input)')
        if type(outputdata) == cls._instance_type.my_input_holder():
            cls._give_inst(outputdata)
        elif cls.conf.stdout: cls._give(outputdata)

    @classmethod
    def get(cls, wait : bool = False) -> MyModuleOutput | None:
        if not cls.conf.stdout: raise Exception(f'{cls.__name__} has no stdout queue')
        if (not wait) and cls._stdout.empty(): return None
        outputdata = cls._stdout.get()
        if type(outputdata) != cls._output_type: raise ValueError(f'{cls.__name__} gave bad output data type. Must be: {cls._output_type}')
        return outputdata

    @classmethod
    def empty_output(cls) -> bool:
        return cls._stdout.empty()

    @classmethod
    def put(cls, inputdata : MyModuleInput):
        if not cls.conf.stdin: raise Exception(f'{cls.__name__} has no stdin queue')
        if type(inputdata) != cls._input_type: raise ValueError(f'bad input data type. {cls.__name__} wants: {cls._input_type}')
        cls._stdin.put(inputdata)

    @classmethod
    def check(cls) -> Exception | None:
        if cls._stderr.empty(): return None
        return cls._stderr.get()

    @classmethod
    def _take(cls) -> MyModuleInput | None:
        if not cls.conf.stdin: raise Exception(f'{cls.__name__} internal stdin error (no stdin queue)')
        if cls._stdin.empty(): return None
        inputdata = cls._stdin.get()
        if type(inputdata) != cls._input_type: raise ValueError(f'{cls.__name__} internal stdin error (wrong type)')
        return inputdata

    @classmethod
    def _give(cls, outputdata : MyModuleOutput):
        if not cls.conf.stdout: raise Exception(f'{cls.__name__} internal stdout error (no stdout queue)')
        if type(outputdata) != cls._output_type: raise ValueError(f'{cls.__name__} internal stdout error (wrong type)')
        cls._stdout.put(outputdata)

    @classmethod
    def _take_inst(cls) -> MyModuleOutput | None:
        if cls.conf.instances_count <= 0: raise Exception(f'{cls.__name__} internal instout error (no instances)')
        if cls._instances_out.empty(): return None
        outputdata = cls._instances_out.get()
        if type(outputdata) != cls._instance_type.my_output_holder(): raise ValueError(f'{cls.__name__} internal instout error (wrong type)')
        return outputdata

    @classmethod
    def _give_inst(cls, inputdata : MyModuleInput):
        if cls.conf.instances_count <= 0: raise Exception(f'{cls.__name__} internal instin error (no instances)')
        if type(inputdata) != cls._instance_type.my_input_holder(): raise ValueError(f'{cls.__name__} internal instin error (wrong type)')
        cls._instances_in.put(inputdata)

    @classmethod
    def wait_if_paused(cls):
       while cls._pause_event.is_set():
            if cls._stop_event.is_set():
                cls.unpause()

    @classmethod
    def pause(cls):
        for i in cls._instances:
            i.pause()
        cls._pause_event.set()
        cls.state.paused = True

    @classmethod
    def unpause(cls):
        if cls.state.has_error:
            raise Exception(f'{cls.__name__} has errors in stderr queue. Handle them before unpausing')
        for i in cls._instances:
            i.unpause()
        cls._pause_event.clear()
        cls.state.paused = False

    @classmethod
    def i_handled_error(cls):
        if not cls._stderr.empty(): raise Exception(f'{cls.__name__} has more errors in stderr queue')
        for i in cls._instances:
            i.i_handled_error()
        cls.state.has_error = False
        cls.unpause()
