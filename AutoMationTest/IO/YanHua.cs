using System;
using System.Collections.Generic;
using System.Text;
using System.Threading;
using Automation.BDaq;

namespace AutoMationTest.IO
{
    public class YanHua
    {
        public Mutex mutex = new Mutex(false);
        public Automation.BDaq.InstantDiCtrl DiCtrl;
        public Automation.BDaq.InstantDoCtrl DoCtrl;
        private byte[] DIdata;
        private byte[] DOdata;
        public int DiCount;
        public int DoCount;
        public bool bConnected = false;


        public YanHua()
        {

            try
            {
                //DiCtrl = new Automation.BDaq.InstantDiCtrl();
                //DoCtrl = new Automation.BDaq.InstantDoCtrl();

                //DiCtrl.SelectedDevice = new DeviceInformation("PCI-1758UDIO,BID#0");
                //DoCtrl.SelectedDevice = new DeviceInformation("PCI-1758UDIO,BID#0");

                //DiCount = DiCtrl.Features.PortCount;
                //DoCount = DoCtrl.Features.PortCount;

                //DIdata = new byte[DiCount];
                //DOdata = new byte[DoCount];

                Thread ReadDIDataThread = new Thread(new ThreadStart(ReadDIData));
                ReadDIDataThread.Start();
                Thread ReadDODataThread = new Thread(new ThreadStart(ReadDOData));
                ReadDODataThread.Start();

                //bConnected = true;
            }
            catch (Exception ex)
            {
                bConnected = false;
            }
        }


        private void ReadDIData()
        {
            while (true)
            {
                //for (int p = 0; p < DiCtrl.Features.PortCount; p++)
                //{
                //DiCtrl.Read(p, out DIdata[p]);
                Thread.Sleep(10);
                //}
            }
        }
        private void ReadDOData()
        {
            while (true)
            {
                //for (int p = 0; p < DoCtrl.Features.PortCount; p++)
                //{
                //DoCtrl.Read(p, out DOdata[p]);
                Thread.Sleep(10);
                //}
            }
        }

        public int GetDI(int port, int n)
        {
            if (!bConnected)
            {
                return -1;
            }
            return (DIdata[port] >> n) & 1;
        }
        public int GetDO(int port, int n)
        {
            if (!bConnected)
            {
                return -1;
            }

            return (DOdata[port] >> n) & 1;
        }
        public void InvertDO(int port, int n)
        {
            if (!bConnected)
            {
                return;
            }
            mutex.WaitOne();
            try
            {
                byte oldData = DOdata[port];
                int mask = 1 << n;
                byte newData = (byte)(oldData ^ mask);
                DoCtrl.Write(port, newData);
            }
            catch (Exception)
            {
                mutex.ReleaseMutex();
            }

            mutex.ReleaseMutex();

        }
        public void SetDO(int port, int n, bool bValue)
        {
            if (!bConnected)
            {
                return;
            }

            mutex.WaitOne();
            try
            {

                byte oldData = DOdata[port];
                byte newData = oldData;

                if (bValue)
                {
                    int mask = 1 << n;
                    newData = (byte)(oldData | mask);
                }
                else
                {
                    int mask = 1 << n;
                    mask = ~mask;
                    newData = (byte)(oldData & mask);
                }

                DoCtrl.Write(port, newData);

                mutex.ReleaseMutex();
            }
            catch (Exception)
            {
                mutex.ReleaseMutex();
            }

        }

    }
}
