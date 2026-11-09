"""Windows-only live-handle ownership. Never terminate a PID read from disk.

Create suspended, assign a non-breakaway kill-on-close Job, persist identity,
then resume. A root exit does not release descendants from the Job. No stale
inventory recovery is attempted. Container cleanup after hard kill is manual.
"""

import ctypes as C
from ctypes import wintypes as W
import os
import shutil
import subprocess
import time


def require_supported_platform():
    if os.name != "nt":
        raise RuntimeError("QA-01 process ownership supports Windows Job Objects only")


class ProcessConstructionError(RuntimeError):
    """Carry retained live ownership to RunOwner when construction cannot return."""

    def __init__(self, message, owned_process):
        super().__init__(message)
        self.owned_process = owned_process


class OwnedProcess:
    def __init__(self, command, *, cwd, env, log, job_name, on_created):
        require_supported_platform()
        import msvcrt

        self.kernel = k = C.WinDLL("kernel32", use_last_error=True)
        self.job = self.process = self.thread = None
        self.closed = False
        self.pid = None
        self.label = job_name
        self.assigned = False
        # No root/tree exists yet. Creation/assignment invalidate these proofs.
        # Closing a handle is NEVER evidence that its process exited.
        self.root_exit_confirmed = True
        self.tree_exit_confirmed = True
        self._auxiliary_handles = []
        self._attributes = None
        self._attribute_storage = None
        self._attributes_initialized = False

        class BasicLimit(C.Structure):
            _fields_ = [("PerProcessUserTimeLimit", C.c_longlong), ("PerJobUserTimeLimit", C.c_longlong),
                        ("LimitFlags", W.DWORD), ("MinimumWorkingSetSize", C.c_size_t),
                        ("MaximumWorkingSetSize", C.c_size_t), ("ActiveProcessLimit", W.DWORD),
                        ("Affinity", C.c_size_t), ("PriorityClass", W.DWORD), ("SchedulingClass", W.DWORD)]

        class Counters(C.Structure):
            _fields_ = [(name, C.c_ulonglong) for name in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount", "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class ExtendedLimit(C.Structure):
            _fields_ = [("BasicLimitInformation", BasicLimit), ("IoInfo", Counters),
                        ("ProcessMemoryLimit", C.c_size_t), ("JobMemoryLimit", C.c_size_t),
                        ("PeakProcessMemoryUsed", C.c_size_t), ("PeakJobMemoryUsed", C.c_size_t)]

        class Startup(C.Structure):
            _fields_ = [("cb", W.DWORD), ("lpReserved", W.LPWSTR), ("lpDesktop", W.LPWSTR),
                        ("lpTitle", W.LPWSTR), ("dwX", W.DWORD), ("dwY", W.DWORD),
                        ("dwXSize", W.DWORD), ("dwYSize", W.DWORD), ("dwXCountChars", W.DWORD),
                        ("dwYCountChars", W.DWORD), ("dwFillAttribute", W.DWORD),
                        ("dwFlags", W.DWORD), ("wShowWindow", W.WORD), ("cbReserved2", W.WORD),
                        ("lpReserved2", C.c_void_p), ("hStdInput", W.HANDLE),
                        ("hStdOutput", W.HANDLE), ("hStdError", W.HANDLE)]

        class StartupEx(C.Structure):
            _fields_ = [("StartupInfo", Startup), ("lpAttributeList", C.c_void_p)]

        class ProcessInfo(C.Structure):
            _fields_ = [("hProcess", W.HANDLE), ("hThread", W.HANDLE), ("dwProcessId", W.DWORD), ("dwThreadId", W.DWORD)]

        signatures = {
            "CreateJobObjectW": ([C.c_void_p, W.LPCWSTR], W.HANDLE),
            "SetInformationJobObject": ([W.HANDLE, C.c_int, C.c_void_p, W.DWORD], W.BOOL),
            "QueryInformationJobObject": ([W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.c_void_p], W.BOOL),
            "AssignProcessToJobObject": ([W.HANDLE, W.HANDLE], W.BOOL),
            "TerminateJobObject": ([W.HANDLE, W.UINT], W.BOOL),
            "CloseHandle": ([W.HANDLE], W.BOOL),
            "GetCurrentProcess": ([], W.HANDLE),
            "DuplicateHandle": ([W.HANDLE, W.HANDLE, W.HANDLE, C.POINTER(W.HANDLE), W.DWORD, W.BOOL, W.DWORD], W.BOOL),
            "InitializeProcThreadAttributeList": ([C.c_void_p, W.DWORD, W.DWORD, C.POINTER(C.c_size_t)], W.BOOL),
            "UpdateProcThreadAttribute": ([C.c_void_p, W.DWORD, C.c_size_t, C.c_void_p, C.c_size_t, C.c_void_p, C.c_void_p], W.BOOL),
            "DeleteProcThreadAttributeList": ([C.c_void_p], None),
            "CreateProcessW": ([W.LPCWSTR, W.LPWSTR, C.c_void_p, C.c_void_p, W.BOOL, W.DWORD, C.c_void_p, W.LPCWSTR, C.POINTER(StartupEx), C.POINTER(ProcessInfo)], W.BOOL),
            "ResumeThread": ([W.HANDLE], W.DWORD),
            "TerminateProcess": ([W.HANDLE, W.UINT], W.BOOL),
            "WaitForSingleObject": ([W.HANDLE, W.DWORD], W.DWORD),
            "GetExitCodeProcess": ([W.HANDLE, C.POINTER(W.DWORD)], W.BOOL),
            "GetProcessTimes": ([W.HANDLE, C.POINTER(W.FILETIME), C.POINTER(W.FILETIME), C.POINTER(W.FILETIME), C.POINTER(W.FILETIME)], W.BOOL),
        }
        for name, (arguments, result) in signatures.items():
            getattr(k, name).argtypes = arguments
            getattr(k, name).restype = result

        def check(value):
            if not value:
                raise C.WinError(C.get_last_error())
            return value

        original_error = None
        try:
            C.set_last_error(0)
            self.job = check(k.CreateJobObjectW(None, job_name))
            if C.get_last_error() == 183:  # ERROR_ALREADY_EXISTS: never adopt another Job
                raise RuntimeError("Refusing existing process Job identity")
            limits = ExtendedLimit()
            limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE; NO breakaway
            check(k.SetInformationJobObject(self.job, 9, C.byref(limits), C.sizeof(limits)))

            with open(os.devnull, "rb") as stdin:
                for name, file in (("stdin", stdin), ("stdout", log)):
                    handle = W.HANDLE()
                    check(k.DuplicateHandle(k.GetCurrentProcess(), msvcrt.get_osfhandle(file.fileno()),
                                            k.GetCurrentProcess(), C.byref(handle), 0, True, 2))
                    self._auxiliary_handles.append((name, handle))
                size = C.c_size_t()
                k.InitializeProcThreadAttributeList(None, 1, 0, C.byref(size))
                self._attribute_storage = C.create_string_buffer(size.value)
                self._attributes = C.cast(self._attribute_storage, C.c_void_p)
                check(k.InitializeProcThreadAttributeList(self._attributes, 1, 0, C.byref(size)))
                self._attributes_initialized = True  # only AFTER the second call succeeds
                handles = (W.HANDLE * 2)(*(handle.value for _, handle in self._auxiliary_handles))
                check(k.UpdateProcThreadAttribute(self._attributes, 0, 0x20002, handles, C.sizeof(handles), None, None))
                startup = StartupEx()
                startup.StartupInfo.cb = C.sizeof(startup)
                startup.StartupInfo.dwFlags = 0x100  # USESTDHANDLES
                startup.StartupInfo.hStdInput = self._auxiliary_handles[0][1]
                startup.StartupInfo.hStdOutput = startup.StartupInfo.hStdError = self._auxiliary_handles[1][1]
                startup.lpAttributeList = self._attributes
                info = ProcessInfo()
                executable = shutil.which(str(command[0]), path=env.get("PATH"))
                if not executable:
                    raise FileNotFoundError(str(command[0]))
                cmdline = C.create_unicode_buffer(subprocess.list2cmdline([executable, *map(str, command[1:])]))
                block = C.create_unicode_buffer("\0".join(f"{key}={value}" for key, value in sorted(env.items(), key=lambda pair: pair[0].upper())) + "\0\0")
                check(k.CreateProcessW(executable, cmdline, None, None, True,
                                      0x4 | 0x400 | 0x80000 | 0x8000000, block, str(cwd), C.byref(startup), C.byref(info)))
                self.process, self.thread, self.pid = info.hProcess, info.hThread, info.dwProcessId
                self.root_exit_confirmed = False
                # No user instruction executes before Job assignment and durable identity.
                check(k.AssignProcessToJobObject(self.job, self.process))
                self.assigned = True
                self.tree_exit_confirmed = False
                created, exited, kernel, user = (W.FILETIME() for _ in range(4))
                check(k.GetProcessTimes(self.process, C.byref(created), C.byref(exited), C.byref(kernel), C.byref(user)))
                on_created({"pid": self.pid, "creation_filetime": (created.dwHighDateTime << 32) | created.dwLowDateTime,
                            "job_name": job_name, "ownership": "live-kernel-job-and-process-handles"})
                if k.ResumeThread(self.thread) == 0xFFFFFFFF:
                    raise C.WinError(C.get_last_error())
        except BaseException as original:
            original_error = original

        # First independent auxiliary release. Failed handles remain owned on self;
        # no DeleteProcThreadAttributeList call for a never-initialized buffer.
        diagnostics = self._release_auxiliary()
        if diagnostics and original_error is None:
            original_error = RuntimeError("Constructor auxiliary handle cleanup failed")
        if original_error is not None:
            try:
                # Includes one further auxiliary close attempt; never leaves a
                # resumed process running merely because constructor cleanup failed.
                self.stop(timeout=10)
            except BaseException as error:
                diagnostics.append(str(error))
                diagnostics.extend(getattr(error, "__notes__", []))
            if diagnostics or not self.closed:
                raise ProcessConstructionError(f"Process creation failed ({original_error}); cleanup diagnostics: {diagnostics}", self) from original_error
            raise original_error

    def _release_auxiliary(self):
        errors = []
        if self._attributes_initialized:
            try:
                self.kernel.DeleteProcThreadAttributeList(self._attributes)
                self._attributes_initialized = False
            except BaseException as error:
                errors.append(f"attribute list cleanup: {error}")
        if not self._attributes_initialized:
            self._attributes = self._attribute_storage = None
        retained = []
        for name, handle in self._auxiliary_handles:
            try:
                if not self.kernel.CloseHandle(handle):
                    raise RuntimeError("CloseHandle returned failure")
            except BaseException as error:
                retained.append((name, handle))
                errors.append(f"{name} duplicate cleanup: {error}")
        self._auxiliary_handles = retained
        return errors

    def poll(self):
        if self.closed:
            raise RuntimeError("Process ownership handle already closed")
        status = self.kernel.WaitForSingleObject(self.process, 0)
        if status == 258:
            return None
        if status != 0:
            raise C.WinError(C.get_last_error())
        code = W.DWORD()
        if not self.kernel.GetExitCodeProcess(self.process, C.byref(code)):
            raise C.WinError(C.get_last_error())
        return code.value

    def wait(self, timeout):
        status = self.kernel.WaitForSingleObject(self.process, max(0, int(timeout * 1000)))
        if status == 258:
            raise subprocess.TimeoutExpired(self.label, timeout)
        if status != 0:
            raise C.WinError(C.get_last_error())
        return self.poll()

    def active_count(self):
        class Accounting(C.Structure):
            _fields_ = [("TotalUserTime", C.c_longlong), ("TotalKernelTime", C.c_longlong),
                        ("ThisPeriodTotalUserTime", C.c_longlong), ("ThisPeriodTotalKernelTime", C.c_longlong),
                        ("TotalPageFaultCount", W.DWORD), ("TotalProcesses", W.DWORD),
                        ("ActiveProcesses", W.DWORD), ("TotalTerminatedProcesses", W.DWORD)]
        accounting = Accounting()
        if not self.kernel.QueryInformationJobObject(self.job, 1, C.byref(accounting), C.sizeof(accounting), None):
            raise C.WinError(C.get_last_error())
        return accounting.ActiveProcesses

    @property
    def cleanup_complete(self):
        return self.closed and self.root_exit_confirmed and self.tree_exit_confirmed

    def stop(self, timeout=10):
        if self.closed:
            if not self.cleanup_complete:
                raise RuntimeError("Closed handles without confirmed process exit; ownership unresolved")
            return
        failure = None
        diagnostics = []

        def attempt(action):
            nonlocal failure
            try:
                action()
            except BaseException as error:
                if failure is None:
                    failure = error
                else:
                    diagnostics.append(str(error))

        def terminate():
            # No poll prerequisite: WAIT_FAILED must not skip our root abort.
            # Never touch a colliding Job that was not assigned our process.
            if self.job and self.assigned and not self.tree_exit_confirmed:
                if not self.kernel.TerminateJobObject(self.job, 1):
                    raise C.WinError(C.get_last_error())
            elif self.process and not self.assigned and not self.root_exit_confirmed:
                if not self.kernel.TerminateProcess(self.process, 1):
                    raise C.WinError(C.get_last_error())

        def confirm_root():
            if self.process and not self.root_exit_confirmed:
                status = self.kernel.WaitForSingleObject(self.process, max(0, int(timeout * 1000)))
                if status == 258:
                    raise subprocess.TimeoutExpired(self.label + " root exit", timeout)
                if status != 0:
                    raise C.WinError(C.get_last_error())
                self.root_exit_confirmed = True

        deadline = time.monotonic() + timeout

        def confirm_tree():
            if self.job and self.assigned and not self.tree_exit_confirmed:
                while self.active_count():
                    if time.monotonic() >= deadline:
                        raise subprocess.TimeoutExpired(self.label + " descendants", timeout)
                    time.sleep(0.02)
                self.tree_exit_confirmed = True

        # A termination failure need not prevent a successful wait or later
        # independent resource release. Preserve the FIRST error, including its type.
        attempt(terminate)
        attempt(confirm_root)
        attempt(confirm_tree)
        attempt(self.close)
        if failure is not None:
            if diagnostics:
                failure.add_note("Further cleanup diagnostics: " + "; ".join(diagnostics))
            raise failure

    def close(self):
        errors = self._release_auxiliary()
        # Retain exact live handles on uncertainty, including an assigned Job.
        # Kill-on-close is not an exit confirmation, nor does it own an unassigned root.
        releasable = {"job": self.tree_exit_confirmed,
                      "thread": self.root_exit_confirmed,
                      "process": self.root_exit_confirmed}
        for name in ("job", "thread", "process"):
            handle = getattr(self, name, None)
            if handle and releasable[name]:
                try:
                    if not self.kernel.CloseHandle(handle):
                        raise RuntimeError("CloseHandle returned failure")
                    setattr(self, name, None)
                except BaseException as error:
                    errors.append(f"{name}: {error}")
        self.closed = not any((self.job, self.thread, self.process, self._auxiliary_handles, self._attributes_initialized))
        if not self.root_exit_confirmed or not self.tree_exit_confirmed:
            errors.append("process exit unresolved; live ownership retained")
        if errors:
            raise RuntimeError("Owned handle close uncertain: " + ", ".join(errors))
