using System;
using System.Collections.Generic;
using System.Text;
using System.Diagnostics;
using System.Management;
//using Microsoft.VisualBasic;

namespace AutoMationTest.Common
{
    public class SysInfo
    {
        static readonly PerformanceCounter cpuCounter = new PerformanceCounter("Processor", "% Processor Time", "_Total");
        static readonly PerformanceCounter ramCounter = new PerformanceCounter("Memory", "Available MBytes");
        static readonly PerformanceCounter uptime = new PerformanceCounter("System", "System Up Time");


        public static bool GetInternetAvilable()
        {
            bool networkUp = System.Net.NetworkInformation.NetworkInterface.GetIsNetworkAvailable();
            return networkUp;
        }

        public static TimeSpan GetSystemUpTime()
        {
            uptime.NextValue();
            TimeSpan ts = TimeSpan.FromSeconds(uptime.NextValue());
            return ts;
        }

        public static string GetPhysicalMemory()
        {
            string str = null;
            ManagementObjectSearcher objCS = new ManagementObjectSearcher("SELECT * FROM Win32_ComputerSystem");
            foreach (ManagementObject objMgmt in objCS.Get())
            {
                str = objMgmt["totalphysicalmemory"].ToString();
            }
            return str;
        }

        public static string getCurrentCpuUsage()
        {
            return cpuCounter.NextValue() + "%";
        }

        public static string getAvailableRAM()
        {
            return ramCounter.NextValue() + "MB";
        }

        public static void GetMemory()
        { 
       
        }

    }
}
