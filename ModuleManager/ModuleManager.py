from queue import Queue
from threading import Thread, Event
from abc import ABC, abstractmethod
from typing import Any, Callable
from pydantic import PositiveInt, BaseModel, Field


class MyModuleConf(BaseModel):
    pass

class MyModuleState(BaseModel):
    started : bool = Field(default=False)
    paused : bool = Field(default=False)
    idle : bool = Field(default=True)

class MyModuleInput(BaseModel):
    pass

class MyModuleOutput(BaseModel):
    pass




class MyModuleInstance(ABC):
    __slots__ = ['_stop_event', '_pause_event', '_main_thread', 'stdin', 'stdout', 'stderr', 'id', 'conf', 'state']

    @abstractmethod
    def my_conf_holder() -> type[MyModuleConf]:
        return MyModuleConf

    @abstractmethod
    def my_state_holder() -> type[MyModuleState]:
        return MyModuleState

    @abstractmethod
    def my_input_holder() -> type[MyModuleInput]:
        return MyModuleInput

    @abstractmethod
    def my_output_holder() -> type[MyModuleOutput]:
        return MyModuleOutput

    @abstractmethod
    def post_init(self) -> None:
        pass

    @abstractmethod
    def post_del(self) -> None:
        pass

    def __init__(self, stdin : Queue, stdout : Queue, stderr : Queue, id : int) -> None:
        self.conf = self.__class__.my_conf_holder()()
        self.state = self.__class__.my_state_holder()()
        self._input_type = self.__class__.my_input_holder()
        self._output_type = self.__class__.my_output_holder()
        self._stop_event = Event()
        self._pause_event = Event()
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.id = id
        self._main_thread = Thread(target=self._main_thread_body, name=self.__class__.__name__+f" id:{self.id} main thread", args=[])
        self._main_thread.start()
        self.state.started = True

    def stop(self):
        self._stop_event.set()
        self._main_thread.join()
        self.post_del()

    def _main_thread_body(self) -> None:
        self.post_init()
        while not self._stop_event.is_set():
            try:
                if self._main_iteration_able_to_perform():
                    self.state.idle = False
                    inputdata = self.stdin.get()
                    if type(inputdata) != self._input_type: raise ValueError(f'bad input data type. Must be: {self._input_type}')
                    outputdata = self.main_thread_iteration(inputdata)
                    if type(outputdata) != self._output_type: raise ValueError(f'bad input data type. Must be: {self._input_type}')
                    self.stdout.put(outputdata)
                self.state.idle = True
                self.wait_if_paused()
            except Exception as err:
                self.state.idle = True
                self.stderr.put(err)
                self.pause()

    def _main_iteration_able_to_perform(self) -> bool:
        return (not self.stdin.empty()) and self.main_thread_iteration_condition()

    def wait_if_paused(self) -> None:
       while self._pause_event.is_set():
            if self._stop_event.is_set():
                self.unpause()

    def pause(self) -> None:
        self._pause_event.set()
        self.state.paused = True

    def unpause(self) -> None:
        self._pause_event.clear()
        self.state.paused = False

    @abstractmethod
    def main_thread_iteration(self, stdin : MyModuleInput) -> MyModuleOutput:
        return None

    @abstractmethod
    def main_thread_iteration_condition(self) -> bool: return True








class MyModule(ABC):
    _main_thread : Thread = None
    _stop_thread_event : Event = None
    _pause_thread_event : Event = None

    _conf : MyModuleConf = None

    state : MyModuleState = None

    stdin : Queue = None
    stdout : Queue = None

    @abstractmethod
    def _pre_custom_init() -> bool: return True

    @abstractmethod
    def _post_custom_init() -> bool: return True

    @abstractmethod
    def _pre_custom_term() -> bool: return True

    @abstractmethod
    def _post_custom_term() -> bool: return True

    @abstractmethod
    def _create_stdin_queue() -> Queue | None: return Queue()

    @abstractmethod
    def _create_stdout_queue() -> Queue | None: return Queue()

    @abstractmethod
    def _create_module_state() -> MyModuleState: return MyModuleState(started=True, booted=False, paused=False, idle=False)

    @abstractmethod
    def _reset_custom_module() -> None: pass

    @classmethod
    def _create_main_thread(cls) -> Thread: return Thread(target=cls._main_thread_body, name=cls.__name__+" main thread", args=[])

    @classmethod
    def _reset_module(cls) -> None:
        cls._reset_custom_module()
        cls._main_thread = None
        cls._stop_thread_event = None
        cls._pause_thread_event = None
        cls._conf = None
        cls.state = None
        cls.stdin = None
        cls.stdout = None

    @classmethod
    def start(cls, conf : MyModuleConf) -> bool:
        if cls.state != None: return False
        if not cls._pre_custom_init(): return False
        cls.state = cls._create_module_state()
        cls.state.started = True
        cls._main_thread = cls._create_main_thread()
        cls._stop_thread_event = Event()
        cls._pause_thread_event = Event()
        cls.stdin = cls._create_stdin_queue()
        cls.stdout = cls._create_stdout_queue()
        cls._conf = conf
        if not cls._post_custom_init():
            cls._reset_module()
            return False
        cls._main_thread.start()
        return True

    @classmethod
    def stop(cls) -> bool:
        if (cls.state == None or cls.state.started == False): return False
        if not cls._pre_custom_term(): return False
        cls._stop_thread_event.set()
        cls._main_thread.join()
        cls._reset_module()
        return cls._post_custom_term()

    @classmethod
    def pause(cls) -> None:
        if (cls.state == None or cls.state.started == False): return False
        cls._pause_thread_event.set()
        cls.state.paused = True

    @classmethod
    def unpause(cls) -> None:
        if (cls.state == None or cls.state.started == False): return False
        cls._pause_thread_event.clear()
        cls.state.paused = False

    @classmethod
    def _wait_for_unpause(cls) -> None:
        if (cls.state == None or cls.state.started == False): return False
        while cls._pause_thread_event.is_set():
            if cls._stop_thread_event.is_set(): break

    @classmethod
    def _main_thread_body(cls) -> None:
        while not cls._stop_thread_event.is_set():
            if cls._main_thread_iteration_condition:
                cls.state.idle = False
                cls._main_thread_iteration()
            cls.state.idle = True
            cls._wait_for_unpause()

    @abstractmethod
    def _main_thread_iteration() -> None: pass

    @classmethod
    @abstractmethod
    def _main_thread_iteration_condition(cls) -> bool: return not cls.stdin.empty()
