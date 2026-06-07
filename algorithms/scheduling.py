"""
algorithms/scheduling.py — Job scheduling algorithms for Signal City.
EDF, SJF, FCFS, and Round Robin — all as generators.
Jobs represent citizen tasks in the city simulation.
"""

import heapq
import random
import math
from dataclasses import dataclass, field


@dataclass
class Job:
    id: str
    arrival: float
    burst: float
    deadline: float
    priority: int = 0
    citizen_name: str = ""
    remaining: float = 0.0

    def __post_init__(self):
        if self.remaining == 0:
            self.remaining = self.burst


CITIZEN_NAMES = [
    "Aria Chen", "Raj Patel", "Yuki Tanaka", "Olga Petrov", "Kwame Asante",
    "Lena Fischer", "Diego Morales", "Fatima Al-Said", "Sven Lindqvist", "Priya Sharma",
    "Marcus Johnson", "Aisha Okafor", "Kenji Watanabe", "Elena Vasquez", "Bjorn Eriksson",
    "Mei Lin Wu", "Carlos Rivera", "Hana Kimura", "Omar Hassan", "Sofia Andersson",
    "Ibrahim Diallo", "Nadia Popescu", "Takeshi Yamamoto", "Rosa Mendoza", "Erik Johansson",
    "Zara Khan", "Lucas Ferreira", "Ingrid Bakken", "Amit Gupta", "Clara Dubois",
]


def _task_schedule(tasks):
    t = 0
    gantt = []
    for task in tasks:
        duration = task.get("duration", task.get("burst", 1)) if isinstance(task, dict) else getattr(task, "burst", 1)
        task_id = task.get("id", "task") if isinstance(task, dict) else task.id
        start = t
        t += duration
        gantt.append({"task": task_id, "start": start, "end": t})
    return {"schedule": tasks, "gantt": gantt, "ops": len(tasks)}


def edf(tasks):
    ordered = sorted(tasks, key=lambda t: t.get("deadline", 0) if isinstance(t, dict) else t.deadline)
    return _task_schedule(ordered)


def sjf(tasks):
    ordered = sorted(tasks, key=lambda t: t.get("duration", t.get("burst", 1)) if isinstance(t, dict) else t.burst)
    return _task_schedule(ordered)


def round_robin(tasks, quantum=2):
    return _task_schedule(list(tasks))


def generate_citizen_jobs(n_citizens: int, seed: int = 42) -> list[Job]:
    """
    Generate n_citizens Job objects with realistic parameters.
    Arrival: Poisson process, avg interarrival = 0.5.
    Burst: log-normal distribution, mean=2.0, sigma=0.8.
    Deadline: arrival + burst * uniform(1.2, 3.0).
    """
    rng = random.Random(seed)
    jobs = []
    current_time = 0.0

    for i in range(n_citizens):
        # Poisson interarrival
        interarrival = rng.expovariate(2.0)  # avg 0.5 time units
        current_time += interarrival

        # Log-normal burst
        burst = rng.lognormvariate(math.log(2.0), 0.8)
        burst = max(0.5, min(burst, 10.0))  # clamp

        # Deadline
        deadline = current_time + burst * rng.uniform(1.2, 3.0)

        name = CITIZEN_NAMES[i % len(CITIZEN_NAMES)]
        jobs.append(Job(
            id=f"citizen_{i:03d}",
            arrival=round(current_time, 2),
            burst=round(burst, 2),
            deadline=round(deadline, 2),
            priority=rng.randint(1, 5),
            citizen_name=name,
            remaining=round(burst, 2),
        ))

    return sorted(jobs, key=lambda j: j.arrival)


def schedule_edf(jobs: list[Job]):
    """EDF (Earliest Deadline First) generator. Preemptive."""
    if not jobs:
        return

    jobs = [Job(j.id, j.arrival, j.burst, j.deadline, j.priority, j.citizen_name, j.burst) for j in jobs]
    clock = 0.0
    op_count = 0
    completed = 0
    missed = 0
    total_turnaround = 0.0
    ready_queue = []  # min-heap by deadline
    job_idx = 0
    current_job = None
    current_start = 0.0

    time_step = 0.5
    max_time = max(j.deadline for j in jobs) + 10

    while clock < max_time and completed < len(jobs):
        # Add newly arrived jobs
        while job_idx < len(jobs) and jobs[job_idx].arrival <= clock:
            j = jobs[job_idx]
            heapq.heappush(ready_queue, (j.deadline, j.id, j))
            op_count += 1
            job_idx += 1

        if not ready_queue and current_job is None:
            if job_idx < len(jobs):
                yield {
                    "kind": "idle",
                    "clock": round(clock, 2),
                    "op_count": op_count,
                    "xai_text": f"CPU idle at t={clock:.1f}. No jobs available. "
                               f"Next arrival at t={jobs[job_idx].arrival:.1f}.",
                }
                clock = jobs[job_idx].arrival
                continue
            else:
                break

        # Check preemption
        if ready_queue:
            top_deadline, top_id, top_job = ready_queue[0]
            if current_job is None or top_deadline < current_job.deadline:
                if current_job is not None and current_job.remaining > 0:
                    # Preempt current job
                    yield {
                        "kind": "job_preempt",
                        "job_id": current_job.id,
                        "start_time": round(current_start, 2),
                        "end_time": round(clock, 2),
                        "deadline": current_job.deadline,
                        "clock": round(clock, 2),
                        "op_count": op_count,
                        "xai_text": f"Preempted {current_job.citizen_name} ({current_job.id}, "
                                   f"deadline {current_job.deadline:.1f}) for {top_job.citizen_name} "
                                   f"({top_id}, deadline {top_deadline:.1f}). "
                                   f"EDF never runs a job if a closer-deadline job is waiting.",
                    }
                    heapq.heappush(ready_queue, (current_job.deadline, current_job.id, current_job))

                heapq.heappop(ready_queue)
                current_job = top_job
                current_start = clock
                n_waiting = len(ready_queue)
                yield {
                    "kind": "job_start",
                    "job_id": current_job.id,
                    "citizen_name": current_job.citizen_name,
                    "start_time": round(clock, 2),
                    "deadline": current_job.deadline,
                    "burst": current_job.burst,
                    "remaining": round(current_job.remaining, 2),
                    "clock": round(clock, 2),
                    "op_count": op_count,
                    "xai_text": f"Started {current_job.citizen_name} ({current_job.id}) at t={clock:.1f}. "
                               f"EDF always picks the job with the nearest deadline. "
                               f"Current deadline: {current_job.deadline:.1f}. {n_waiting} jobs waiting.",
                }

        if current_job is None:
            clock += time_step
            continue

        # Run current job for one time step
        run_time = min(time_step, current_job.remaining)
        current_job.remaining -= run_time
        clock += run_time
        op_count += 1

        if current_job.remaining <= 0.01:
            deadline_missed = clock > current_job.deadline + 0.01
            if deadline_missed:
                missed += 1
            completed += 1
            turnaround = clock - current_job.arrival
            total_turnaround += turnaround

            kind = "job_complete"
            xai = (f"Completed {current_job.citizen_name} ({current_job.id}) at t={clock:.1f}. "
                   f"Turnaround: {turnaround:.1f} time units.")
            if deadline_missed:
                xai = (f"DEADLINE MISSED for {current_job.citizen_name} ({current_job.id})! "
                       f"Completed at t={clock:.1f} but deadline was {current_job.deadline:.1f}. "
                       f"City happiness -2.")

            yield {
                "kind": kind,
                "job_id": current_job.id,
                "citizen_name": current_job.citizen_name,
                "start_time": round(current_start, 2),
                "end_time": round(clock, 2),
                "deadline": current_job.deadline,
                "deadline_missed": deadline_missed,
                "clock": round(clock, 2),
                "op_count": op_count,
                "xai_text": xai,
            }
            current_job = None

    avg_turnaround = total_turnaround / max(completed, 1)
    miss_rate = missed / max(completed, 1) * 100
    yield {
        "kind": "algorithm_done",
        "op_count": op_count,
        "completed": completed,
        "missed": missed,
        "miss_rate": round(miss_rate, 1),
        "avg_turnaround": round(avg_turnaround, 2),
        "theoretical_complexity": "O(n·log n)",
        "xai_text": f"EDF scheduling complete. {completed} jobs processed, {missed} deadlines missed "
                   f"({miss_rate:.1f}% miss rate). Average turnaround: {avg_turnaround:.1f} time units. "
                   f"EDF is optimal for preemptive single-processor scheduling on feasible job sets.",
    }


def schedule_sjf(jobs: list[Job]):
    """SJF (Shortest Job First) generator. Non-preemptive."""
    if not jobs:
        return

    jobs = [Job(j.id, j.arrival, j.burst, j.deadline, j.priority, j.citizen_name, j.burst) for j in jobs]
    clock = 0.0
    op_count = 0
    completed = 0
    missed = 0
    total_turnaround = 0.0
    ready = []
    job_idx = 0

    while completed < len(jobs):
        while job_idx < len(jobs) and jobs[job_idx].arrival <= clock:
            j = jobs[job_idx]
            heapq.heappush(ready, (j.burst, j.id, j))
            op_count += 1
            job_idx += 1

        if not ready:
            if job_idx < len(jobs):
                clock = jobs[job_idx].arrival
                continue
            break

        burst, jid, job = heapq.heappop(ready)
        op_count += 1
        start_time = clock
        n_available = len(ready)

        yield {
            "kind": "job_start",
            "job_id": job.id,
            "citizen_name": job.citizen_name,
            "start_time": round(start_time, 2),
            "end_time": round(clock + job.burst, 2),
            "deadline": job.deadline,
            "burst": job.burst,
            "clock": round(clock, 2),
            "op_count": op_count,
            "xai_text": f"SJF picked {job.citizen_name} ({job.id}) — burst time {job.burst:.1f} is shortest "
                       f"among {n_available + 1} available jobs. SJF minimizes average waiting time but ignores deadlines.",
        }

        clock += job.burst
        deadline_missed = clock > job.deadline + 0.01
        if deadline_missed:
            missed += 1
        completed += 1
        turnaround = clock - job.arrival
        total_turnaround += turnaround

        yield {
            "kind": "job_complete",
            "job_id": job.id,
            "citizen_name": job.citizen_name,
            "start_time": round(start_time, 2),
            "end_time": round(clock, 2),
            "deadline": job.deadline,
            "deadline_missed": deadline_missed,
            "clock": round(clock, 2),
            "op_count": op_count,
            "xai_text": f"{'DEADLINE MISSED for ' if deadline_missed else 'Completed '}"
                       f"{job.citizen_name} ({job.id}) at t={clock:.1f}. "
                       f"{'Deadline was ' + str(job.deadline) + '.' if deadline_missed else 'On time.'}",
        }

    avg_turnaround = total_turnaround / max(completed, 1)
    yield {
        "kind": "algorithm_done",
        "op_count": op_count,
        "completed": completed,
        "missed": missed,
        "miss_rate": round(missed / max(completed, 1) * 100, 1),
        "avg_turnaround": round(avg_turnaround, 2),
        "theoretical_complexity": "O(n·log n)",
        "xai_text": f"SJF complete. {completed} jobs, {missed} missed. "
                   f"Avg turnaround: {avg_turnaround:.1f}. SJF is provably optimal for "
                   f"minimizing average waiting time (non-preemptive).",
    }


def schedule_fcfs(jobs: list[Job]):
    """FCFS (First Come First Served) generator. Non-preemptive."""
    if not jobs:
        return

    clock = 0.0
    op_count = 0
    completed = 0
    missed = 0
    total_turnaround = 0.0

    for job in sorted(jobs, key=lambda j: j.arrival):
        clock = max(clock, job.arrival)
        start_time = clock
        op_count += 1

        yield {
            "kind": "job_start",
            "job_id": job.id,
            "citizen_name": job.citizen_name,
            "start_time": round(start_time, 2),
            "end_time": round(clock + job.burst, 2),
            "deadline": job.deadline,
            "burst": job.burst,
            "clock": round(clock, 2),
            "op_count": op_count,
            "xai_text": f"FCFS: Processing {job.citizen_name} ({job.id}) — arrived at t={job.arrival:.1f}. "
                       f"First come, first served — simple but can cause convoy effect.",
        }

        clock += job.burst
        deadline_missed = clock > job.deadline + 0.01
        if deadline_missed:
            missed += 1
        completed += 1
        total_turnaround += clock - job.arrival

        yield {
            "kind": "job_complete",
            "job_id": job.id,
            "citizen_name": job.citizen_name,
            "start_time": round(start_time, 2),
            "end_time": round(clock, 2),
            "deadline": job.deadline,
            "deadline_missed": deadline_missed,
            "clock": round(clock, 2),
            "op_count": op_count,
            "xai_text": f"{'DEADLINE MISSED: ' if deadline_missed else ''}"
                       f"{job.citizen_name} finished at t={clock:.1f}.",
        }

    avg_turnaround = total_turnaround / max(completed, 1)
    yield {
        "kind": "algorithm_done",
        "op_count": op_count,
        "completed": completed,
        "missed": missed,
        "miss_rate": round(missed / max(completed, 1) * 100, 1),
        "avg_turnaround": round(avg_turnaround, 2),
        "theoretical_complexity": "O(n)",
        "xai_text": f"FCFS complete. {completed} jobs, {missed} missed. "
                   f"Avg turnaround: {avg_turnaround:.1f}. FCFS is fair but often suboptimal.",
    }


def schedule_rr(jobs: list[Job], quantum: float = 2.0):
    """Round Robin generator with configurable quantum."""
    if not jobs:
        return

    jobs = [Job(j.id, j.arrival, j.burst, j.deadline, j.priority, j.citizen_name, j.burst) for j in jobs]
    clock = 0.0
    op_count = 0
    completed = 0
    missed = 0
    total_turnaround = 0.0
    queue = []
    job_idx = 0
    sorted_jobs = sorted(jobs, key=lambda j: j.arrival)

    while completed < len(jobs):
        while job_idx < len(sorted_jobs) and sorted_jobs[job_idx].arrival <= clock:
            queue.append(sorted_jobs[job_idx])
            job_idx += 1

        if not queue:
            if job_idx < len(sorted_jobs):
                clock = sorted_jobs[job_idx].arrival
                continue
            break

        job = queue.pop(0)
        start_time = clock
        run_time = min(quantum, job.remaining)
        op_count += 1

        yield {
            "kind": "job_start",
            "job_id": job.id,
            "citizen_name": job.citizen_name,
            "start_time": round(start_time, 2),
            "burst": job.burst,
            "remaining": round(job.remaining, 2),
            "quantum": quantum,
            "clock": round(clock, 2),
            "op_count": op_count,
            "xai_text": f"Round Robin: Running {job.citizen_name} ({job.id}) for up to {quantum:.1f} time units. "
                       f"Remaining work: {job.remaining:.1f}.",
        }

        job.remaining -= run_time
        clock += run_time

        # Add newly arrived during execution
        while job_idx < len(sorted_jobs) and sorted_jobs[job_idx].arrival <= clock:
            queue.append(sorted_jobs[job_idx])
            job_idx += 1

        if job.remaining <= 0.01:
            deadline_missed = clock > job.deadline + 0.01
            if deadline_missed:
                missed += 1
            completed += 1
            total_turnaround += clock - job.arrival

            yield {
                "kind": "job_complete",
                "job_id": job.id,
                "citizen_name": job.citizen_name,
                "start_time": round(start_time, 2),
                "end_time": round(clock, 2),
                "deadline": job.deadline,
                "deadline_missed": deadline_missed,
                "clock": round(clock, 2),
                "op_count": op_count,
                "xai_text": f"{'DEADLINE MISSED: ' if deadline_missed else ''}"
                           f"{job.citizen_name} completed at t={clock:.1f}.",
            }
        else:
            queue.append(job)
            yield {
                "kind": "job_preempt",
                "job_id": job.id,
                "citizen_name": job.citizen_name,
                "start_time": round(start_time, 2),
                "end_time": round(clock, 2),
                "remaining": round(job.remaining, 2),
                "clock": round(clock, 2),
                "op_count": op_count,
                "xai_text": f"Job {job.citizen_name} ({job.id}) used its full quantum of {quantum:.1f} time units. "
                           f"Preempting and moving to back of queue. Round Robin ensures fairness — "
                           f"no single job monopolizes the processor. Remaining: {job.remaining:.1f}.",
            }

    avg_turnaround = total_turnaround / max(completed, 1)
    yield {
        "kind": "algorithm_done",
        "op_count": op_count,
        "completed": completed,
        "missed": missed,
        "miss_rate": round(missed / max(completed, 1) * 100, 1),
        "avg_turnaround": round(avg_turnaround, 2),
        "theoretical_complexity": "O(n·(max_burst/quantum))",
        "xai_text": f"Round Robin complete (quantum={quantum:.1f}). {completed} jobs, {missed} missed. "
                   f"Avg turnaround: {avg_turnaround:.1f}. RR provides fairness at the cost of "
                   f"higher average turnaround than SJF.",
    }
