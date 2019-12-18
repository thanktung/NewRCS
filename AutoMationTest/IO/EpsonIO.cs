using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using AutoMationTest.Common;
using System.Windows.Forms;

namespace AutoMationTest.IO
{
    public class EpsonIO
    {
        public int GetInput(int num)
        {
            if (Produce.Epson != null && Robots.Robot.IsConnected)
            {

                try
                {
                    string sreceive = "";
                    //MessageBox.Show("geti," + num.ToString() + ",0");
                    Produce.Epson.SendReadEpson202("geti," + num.ToString() + ",0", "i" + num.ToString() + "_", ref sreceive);
                    //MessageBox.Show("0");
                    string get = sreceive.Trim().Split('_')[1].Replace(" ", "").Replace("\t", "").Replace("\n", "").Replace("\r", "").Trim();
                    //MessageBox.Show(get);
                    if (get.Equals("1"))
                    {
                        return 1;
                    }
                    else
                    {
                        return 0;
                    }
                }
                catch (Exception ex)
                {
                    return -1;
                }
            }
            else
            {
                return -1;
            }
        }

        public int GetOutput(int num)
        {
            if (Produce.Epson != null && Robots.Robot.IsConnected)
            {
                try
                {
                    string sreceive = "";
                    Produce.Epson.SendReadEpson202("geto," + num.ToString() + ",0", "o" + num.ToString() + "_", ref sreceive);
                    string get = sreceive.Trim().Split('_')[1].Replace(" ", "").Replace("\t", "").Replace("\n", "").Replace("\r", "").Trim();
                    if (get.Equals("1"))
                    {
                        return 1;
                    }
                    else
                    {
                        return 0;
                    }
                }
                catch (Exception ex)
                {
                    return -1;
                }
            }
            else
            {
                return -1;
            }
        }

        public void SetOutput(int num, bool bonoff)
        {
            if (Produce.Epson != null && Robots.Robot.IsConnected)
            {
                try
                {

                    if (bonoff)
                        Produce.Epson.SendEpson202("set," + num.ToString() + ",1");
                    else
                        Produce.Epson.SendEpson202("set," + num.ToString() + ",0");
                }
                catch (Exception ex)
                {
                    return;
                }
            }
        }
    }
}
