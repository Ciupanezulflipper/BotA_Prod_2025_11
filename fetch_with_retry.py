#!/usr/bin/env python3
"""
Retry wrapper for API calls with exponential backoff
Handles empty DataFrames, network errors, rate limits
"""

import time
import functools
from typing import Callable, Any, Optional
from datetime import datetime
import pandas as pd


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 2.0,
    backoff_factor: float = 2.0,
    max_delay: float = 30.0,
    exceptions: tuple = (Exception,),
    check_empty_df: bool = True
):
    """
    Decorator to retry function calls with exponential backoff
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        backoff_factor: Multiplier for delay after each retry
        max_delay: Maximum delay between retries
        exceptions: Tuple of exceptions to catch
        check_empty_df: If True, treat empty DataFrames as failure
    
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    # Call the function
                    result = func(*args, **kwargs)
                    
                    # Check if result is an empty DataFrame (if enabled)
                    if check_empty_df and isinstance(result, pd.DataFrame):
                        if result.empty:
                            print(f"⚠️  [{datetime.now():%H:%M:%S}] Empty DataFrame on attempt {attempt + 1}/{max_retries}")
                            if attempt < max_retries - 1:
                                time.sleep(min(delay, max_delay))
                                delay *= backoff_factor
                            continue
                    
                    # Success - return result
                    if attempt > 0:
                        print(f"✅ [{datetime.now():%H:%M:%S}] Success after {attempt + 1} attempts")
                    return result
                    
                except exceptions as e:
                    last_exception = e
                    print(f"❌ [{datetime.now():%H:%M:%S}] Attempt {attempt + 1}/{max_retries} failed: {type(e).__name__}: {str(e)[:100]}")
                    
                    # Don't sleep after last attempt
                    if attempt < max_retries - 1:
                        sleep_time = min(delay, max_delay)
                        print(f"😴 Sleeping {sleep_time:.1f}s before retry...")
                        time.sleep(sleep_time)
                        delay *= backoff_factor
            
            # All retries exhausted
            print(f"🛑 [{datetime.now():%H:%M:%S}] All {max_retries} attempts failed")
            if last_exception:
                raise last_exception
            return None
        
        return wrapper
    return decorator


def fetch_with_retry(
    fetch_func: Callable,
    *args,
    max_retries: int = 3,
    **kwargs
) -> Optional[Any]:
    """
    Convenience function to apply retry logic without decorator
    
    Args:
        fetch_func: Function to call
        *args: Positional arguments for fetch_func
        max_retries: Number of retry attempts
        **kwargs: Keyword arguments for fetch_func
    
    Returns:
        Result from fetch_func or None if all retries fail
    """
    @retry_with_backoff(max_retries=max_retries)
    def wrapped():
        return fetch_func(*args, **kwargs)
    
    return wrapped()


# Test function for validation
def _test_retry():
    """Self-test for retry logic"""
    print("\n=== Testing Retry Logic ===\n")
    
    # Test 1: Successful call
    print("Test 1: Immediate success")
    @retry_with_backoff(max_retries=3, initial_delay=0.5)
    def success_func():
        return pd.DataFrame({'a': [1, 2, 3]})
    
    result = success_func()
    assert not result.empty, "Test 1 failed: result is empty"
    print("✅ Test 1 passed\n")
    
    # Test 2: Empty DataFrame retry
    print("Test 2: Empty DataFrame with eventual success")
    attempt_counter = [0]
    
    @retry_with_backoff(max_retries=3, initial_delay=0.5, check_empty_df=True)
    def empty_then_success():
        attempt_counter[0] += 1
        if attempt_counter[0] < 2:
            return pd.DataFrame()  # Empty first time
        return pd.DataFrame({'b': [4, 5, 6]})
    
    result = empty_then_success()
    assert not result.empty, "Test 2 failed: result is empty"
    assert attempt_counter[0] == 2, f"Test 2 failed: expected 2 attempts, got {attempt_counter[0]}"
    print("✅ Test 2 passed\n")
    
    # Test 3: Exception handling
    print("Test 3: Exception with retry")
    exception_counter = [0]
    
    @retry_with_backoff(max_retries=3, initial_delay=0.5, exceptions=(ValueError,))
    def exception_then_success():
        exception_counter[0] += 1
        if exception_counter[0] < 3:
            raise ValueError("Simulated API error")
        return pd.DataFrame({'c': [7, 8, 9]})
    
    result = exception_then_success()
    assert not result.empty, "Test 3 failed: result is empty"
    assert exception_counter[0] == 3, f"Test 3 failed: expected 3 attempts, got {exception_counter[0]}"
    print("✅ Test 3 passed\n")
    
    print("=== All Tests Passed ===\n")


if __name__ == "__main__":
    _test_retry()
