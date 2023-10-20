# Parallel Ping Testing
## Description:
Run concurrent ping tests to a chosen destinations using the asyncio library.

The script takes the entries from the hosts.json file and creates a task for each.
Hosts structure:
```
"destination": {  
  "timeout": int,  
  "sleep_period": int,  
  "count": int,  
  "max_rtt": int,  
  "packet_size": int  
}
```

**timeout** - ICMP timeout.  
**sleep_period** - Seconds between each ping action.  
**count** - Number of ping requests per action.  
**max_rtt** - Maximum Round Trip Time consdered for a successful request.  
**packet_size** - Size of each packet.  

The script is actively monitoring for any changes in the hosts.json file which means that you can add or delete destinations or modify the options for an already existing entry, while the program is running.

## Changelog:
23-Aug-2023
- Improved the way the script checks if the destination is a valid IPv4 address.
- Improved the DNS function.
- Code clean up in pyping.py.

22-Aug-2023
- Implemented packet size in the hosts file.
- Fixed the file handler.
- Fixed some logging problems.
- Code clean up in pyping.py.

## Resources used:
- https://stackoverflow.com/questions/32313989/check-specific-file-has-been-modified-using-python-watchdog
- https://github.com/toxinu/Pyping/
- https://www.roguelynn.com/words/asyncio-graceful-shutdowns/
