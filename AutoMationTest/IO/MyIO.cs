using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using AutoMationTest.Common;
using System.Collections;
using System.Windows.Forms;
using System.Threading;

namespace AutoMationTest.IO
{
    public class MyIO
    {

        public enum IOType
        {
            YanHua,
            Epson
        }



        public IOType MyIOName;

        YanHua _yanhua;
        EpsonIO _epsonio;
        public int InputCount = 0;
        public int OutputCount = 0;
        public ArrayList InputList = new ArrayList();
        public ArrayList OutputList = new ArrayList();
        private Hashtable epsoninlist = new Hashtable();
        private Hashtable epsonoutlist = new Hashtable();

        public MyIO(IOType _type)
        {
            MyIOName = _type;

            switch (_type)
            {
                case IOType.YanHua:
                    _yanhua = new YanHua();
                    break;
                case IOType.Epson:
                    _epsonio = new EpsonIO();
                    break;
                default:
                    _yanhua = new YanHua();
                    break;
            }

            InputCount = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "IO", "Input", "Count", "0"));
            OutputCount = Convert.ToInt32(INI.ReadINI(Application.StartupPath + "\\Data", "IO", "Output", "Count", "0"));


            for (int i = 0; i < InputCount; i++)
            {
                string inset = "";
                string inputname = INI.ReadINI(Application.StartupPath + "\\Data", "IO", "Input", "In_" + Convert.ToString(i + 1), "Input" + Convert.ToString(i + 1));
                if (MyIOName == IOType.YanHua)
                {
                    inset = INI.ReadINI(Application.StartupPath + "\\Data", "IO", "YANHUA_Input", inputname, "0,0");
                }
                else if (MyIOName == IOType.Epson)
                {
                    inset = INI.ReadINI(Application.StartupPath + "\\Data", "IO", "Epson_Input", inputname, "0");
                }
                InputList.Add(inputname + "," + inset);
            }

            for (int j = 0; j < OutputCount; j++)
            {
                string outset = "";
                string outputname = INI.ReadINI(Application.StartupPath + "\\Data", "IO", "Output", "Out_" + Convert.ToString(j + 1), "Output" + Convert.ToString(j + 1));
                if (MyIOName == IOType.YanHua)
                {
                    outset = INI.ReadINI(Application.StartupPath + "\\Data", "IO", "YANHUA_Output", outputname, "0,0");
                }
                else if (MyIOName == IOType.Epson)
                {
                    outset = INI.ReadINI(Application.StartupPath + "\\Data", "IO", "Epson_Output", outputname, "0");
                }
                OutputList.Add(outputname + "," + outset);
            }

            if (MyIOName == IOType.Epson)
            {
                Thread thd = new Thread(new ThreadStart(getepsonio));
                thd.Start();
            }
        }

        private void getepsonio()
        {
            while (true)
            {
                for (int i = 0; i < InputList.Count; i++)
                {
                    try
                    {
                        //MessageBox.Show("1");
                        int num = Convert.ToInt16(InputList[i].ToString().Split(',')[1]);
                        int result = _epsonio.GetInput(num);
                        //MessageBox.Show("2");
                        if (!epsoninlist.Contains(i))
                        {
                            epsoninlist.Add(i, result);
                        }
                        else
                        {
                            epsoninlist[i] = result;
                        }
                    }
                    catch (Exception ex)
                    {
                        MessageBox.Show(ex.ToString());
                    }
                    Thread.Sleep(10);
                }

                for (int j = 0; j < OutputList.Count; j++)
                {
                    try
                    {
                        int num = Convert.ToInt16(OutputList[j].ToString().Split(',')[1]);
                        int result = _epsonio.GetOutput(num);
                        if (!epsonoutlist.Contains(j))
                        {
                            epsonoutlist.Add(j, result);
                        }
                        else
                        {
                            epsonoutlist[j] = result;
                        }
                    }
                    catch (Exception ex)
                    {
                        MessageBox.Show(ex.ToString());
                    }

                    Thread.Sleep(10);
                }

                Thread.Sleep(10);
            }
        }

        //public void AddInput(string Inname)
        //{
        //    InputCount++;
        //    INI.WriteINI(Application.StartupPath + "\\Data","IO", "Input", "Count", InputCount.ToString());
        //    INI.WriteINI(Application.StartupPath + "\\Data","IO", "Input", "In_" + InputCount.ToString(), Inname);
        //    InputList.Add(Inname);
        //}

        public void DeleteInput()
        {
            if (InputCount > 0)
            {
                string tname = INI.ReadINI(Application.StartupPath + "\\Data", "IO", "Input", "In_" + InputCount.ToString(), "");
                INI.WriteINI(Application.StartupPath + "\\Data", "IO", "Input", "In_" + InputCount.ToString(), "");
                if (MyIOName == IOType.YanHua)
                {
                    INI.WriteINI(Application.StartupPath + "\\Data", "IO", "YANHUA_Input", tname, "0,0");
                }
                else if (MyIOName == IOType.Epson)
                {
                    INI.WriteINI(Application.StartupPath + "\\Data", "IO", "Epson_Input", tname, "0");
                }
                InputCount--;
                INI.WriteINI(Application.StartupPath + "\\Data", "IO", "Input", "Count", InputCount.ToString());

                InputList.RemoveAt(InputList.Count - 1);
            }
        }



        public void DeleteOutput()
        {
            if (OutputCount > 0)
            {
                string tname = INI.ReadINI(Application.StartupPath + "\\Data", "IO", "Output", "Out_" + OutputCount.ToString(), "");
                INI.WriteINI(Application.StartupPath + "\\Data", "IO", "Output", "Out_" + OutputCount.ToString(), "");
                if (MyIOName == IOType.YanHua)
                {
                    INI.WriteINI(Application.StartupPath + "\\Data", "IO", "YANHUA_Output", tname, "0,0");
                }
                else if (MyIOName == IOType.Epson)
                {
                    INI.WriteINI(Application.StartupPath + "\\Data", "IO", "Epson_Output", tname, "0");
                }
                OutputCount--;
                INI.WriteINI(Application.StartupPath + "\\Data", "IO", "Output", "Count", OutputCount.ToString());

                OutputList.RemoveAt(OutputList.Count - 1);
            }
        }

        //public static string GetInputName(int index)
        //{
        //    string sread = INI.ReadINI(Application.StartupPath + "\\Data","IO", "Input", "In_" + index.ToString(), "Input" + index.ToString());
        //    return sread;
        //}

        //public static string GetOutputName(int index)
        //{
        //    string sread = INI.ReadINI(Application.StartupPath + "\\Data","IO", "Output", "Out_" + index.ToString(), "Output" + index.ToString());
        //    return sread;
        //}



        public void GetInputPortNum(int index, ref  string inputname, ref int port, ref int num)
        {
            if (MyIOName == IOType.YanHua)
            {

                inputname = INI.ReadINI(Application.StartupPath + "\\Data", "IO", "Input", "In_" + index.ToString(), "Input" + index.ToString());
                string sread = INI.ReadINI(Application.StartupPath + "\\Data", "IO", "YANHUA_Input", inputname, "0,0");
                try
                {
                    port = Convert.ToInt32(sread.Split(',')[0]);
                    num = Convert.ToInt32(sread.Split(',')[1]);
                }
                catch (Exception ex)
                {
                    port = 0;
                    num = 0;
                }
            }
        }

        public void GetInputNum(int index, ref  string inputname, ref int num)
        {
            if (MyIOName == IOType.Epson)
            {

                inputname = INI.ReadINI(Application.StartupPath + "\\Data", "IO", "Input", "In_" + index.ToString(), "Input" + index.ToString());
                string sread = INI.ReadINI(Application.StartupPath + "\\Data", "IO", "Epson_Input", inputname, "0");
                try
                {
                    num = Convert.ToInt32(sread);
                }
                catch (Exception ex)
                {
                    num = 0;
                }
            }
        }



        public void SetInputPortNum(int index, string inputname, string port, string num)
        {
            if (index < InputCount + 1)
            {
                return;
            }
            if (MyIOName == IOType.YanHua)
            {
                INI.WriteINI(Application.StartupPath + "\\Data", "IO", "Input", "In_" + index.ToString(), inputname);
                INI.WriteINI(Application.StartupPath + "\\Data", "IO", "YANHUA_Input", inputname, port + "," + num);

                InputCount++;
                INI.WriteINI(Application.StartupPath + "\\Data", "IO", "Input", "Count", InputCount.ToString());
                InputList.Add(inputname + "," + port + "," + num);
            }

        }

        public void SetInputNum(int index, string inputname, string num)
        {
            if (index < InputCount + 1)
            {
                return;
            }
            if (MyIOName == IOType.Epson)
            {
                INI.WriteINI(Application.StartupPath + "\\Data", "IO", "Input", "In_" + index.ToString(), inputname);
                INI.WriteINI(Application.StartupPath + "\\Data", "IO", "Epson_Input", inputname, num);

                InputCount++;
                INI.WriteINI(Application.StartupPath + "\\Data", "IO", "Input", "Count", InputCount.ToString());
                InputList.Add(inputname + "," + num);
            }

        }

        public void GetOutputPortNum(int index, ref string outputname, ref int port, ref int num)
        {
            outputname = INI.ReadINI(Application.StartupPath + "\\Data", "IO", "Output", "Out_" + index.ToString(), "Output" + index.ToString());
            string sread = INI.ReadINI(Application.StartupPath + "\\Data", "IO", "YANHUA_Output", outputname, "0,0");
            try
            {
                port = Convert.ToInt32(sread.Split(',')[0]);
                num = Convert.ToInt32(sread.Split(',')[1]);
            }
            catch (Exception ex)
            {
                port = 0;
                num = 0;
            }
        }

        public void GetOutputNum(int index, ref string outputname, ref int num)
        {
            outputname = INI.ReadINI(Application.StartupPath + "\\Data", "IO", "Output", "Out_" + index.ToString(), "Output" + index.ToString());
            string sread = INI.ReadINI(Application.StartupPath + "\\Data", "IO", "Epson_Output", outputname, "0");
            try
            {
                num = Convert.ToInt32(sread);
            }
            catch (Exception ex)
            {
                num = 0;
            }
        }

        public void SetOutputPortNum(int index, string outputname, string port, string num)
        {
            if (index < OutputCount + 1)
            {
                return;
            }

            INI.WriteINI(Application.StartupPath + "\\Data", "IO", "Output", "Out_" + index.ToString(), outputname);
            INI.WriteINI(Application.StartupPath + "\\Data", "IO", "YANHUA_Output", outputname, port + "," + num);

            OutputCount++;
            INI.WriteINI(Application.StartupPath + "\\Data", "IO", "Output", "Count", OutputCount.ToString());
            OutputList.Add(outputname + "," + port + "," + num);

        }

        public void SetOutputNum(int index, string outputname, string num)
        {
            if (index < OutputCount + 1)
            {
                return;
            }

            if (MyIOName == IOType.Epson)
            {
                INI.WriteINI(Application.StartupPath + "\\Data", "IO", "Output", "Out_" + index.ToString(), outputname);
                INI.WriteINI(Application.StartupPath + "\\Data", "IO", "Epson_Output", outputname, num);
                OutputCount++;
                INI.WriteINI(Application.StartupPath + "\\Data", "IO", "Output", "Count", OutputCount.ToString());
                OutputList.Add(outputname + "," + num);

            }

        }

        public int ReadInput(int inputindex)
        {
            int port = 0;
            int num = 0;

            if (inputindex > InputList.Count - 1)
            {
                return -1;
            }

            string[] ssplit = InputList[inputindex].ToString().Split(',');


            switch (MyIOName)
            {

                case IOType.YanHua:
                    port = Convert.ToInt16(ssplit[1]);
                    num = Convert.ToInt16(ssplit[2]);
                    return _yanhua.GetDI(port, num);

                case IOType.Epson:
                    //num = Convert.ToInt16(ssplit[1]);
                    try
                    {
                        return Convert.ToInt16(epsoninlist[inputindex]);
                    }
                    catch (Exception ex)
                    {
                        return -1;
                    }
                default:
                    return -1;
            }
        }


        public int ReadOutput(int outindex)
        {
            int port = 0;
            int num = 0;

            if (outindex > InputList.Count - 1)
            {
                return -1;
            }

            string[] ssplit = OutputList[outindex].ToString().Split(',');


            switch (MyIOName)
            {
                case IOType.YanHua:
                    port = Convert.ToInt16(ssplit[1]);
                    num = Convert.ToInt16(ssplit[2]);
                    return _yanhua.GetDO(port, num);

                case IOType.Epson:
                    //num = Convert.ToInt16(ssplit[1]);
                    try
                    {
                        return Convert.ToInt16(epsonoutlist[outindex]);
                    }
                    catch (Exception ex)
                    {
                        return -1;
                    }
                default:
                    return -1;
            }
        }

        public void SetOutput(int outindex, bool bon)
        {
            int port = 0;
            int num = 0;

            if (outindex > InputList.Count - 1)
            {
                return;
            }

            string[] ssplit = OutputList[outindex].ToString().Split(',');



            switch (MyIOName)
            {
                case IOType.YanHua:
                    port = Convert.ToInt16(ssplit[1]);
                    num = Convert.ToInt16(ssplit[2]);
                    _yanhua.SetDO(port, num, bon);
                    break;

                case IOType.Epson:
                    num = Convert.ToInt16(ssplit[1]);
                    _epsonio.SetOutput(num, bon);
                    break;

                default:
                    break;
            }
        }
    }
}
