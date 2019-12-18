using System;
using System.Collections.Generic;
using System.Text;
using System.Windows.Forms;
using System.Collections;

namespace AutoMationTest.Function
{
    public class CycleQueue
    {
        //如果是普通隊列，新增元素，隊尾rear只用加1就行；如果是循環隊列，rear + 1後求Max的餘數
        //簡單來說，普通隊列任何計算的 x++ 就等於循環隊列的 （x+1) % max

        object[] data;//數據元素
        private int Max;//最大容量
        private int front;//指向隊頭
        private int rear;//指向隊尾

        public object Doing;
        public int Count;

        //public ATS_Client.Action DoingQueueElement;
        public CycleQueue(int Max)
        {
            this.Max = Max;
            front = rear = 0; //此處為循環隊列，普通隊列為-1；
            data = new object[Max];

        }

        public int MaxSize
        {
            get
            {
                return this.Max;
            }
            set
            {
                this.Max = value;
            }

        }

        public int Rear
        {
            get
            {
                return this.rear;
            }
            set
            {
                this.rear = value;
            }

        }

        public int Front
        {
            get
            {
                return this.front;
            }
            set
            {
                this.front = value;
            }

        }

        public object this[int index]
        {
            get
            {

                if (IsEmpty())
                {
                    return null;
                }

                int addindex = 0;
                int i = (front + 1) % Max;

                while (i != (rear + 1) % Max)
                {
                    if (index == addindex)
                    {
                        object temp = data[i];
                        return temp;
                    }
                    i = (i + 1) % Max;
                    addindex++;
                }

                return null;
            }

        }

        public int GetQueueLength()
        {
            //return rear - front;
            return (rear - front + Max) % Max;
        }

        public bool IsFull()
        {
            if ((rear + 1) % Max == front)//(GetQueueLength() == Max)
            {
                return true;
            }
            else
            {
                return false;
            }
        }

        public bool IsEmpty()
        {
            if (rear == front)
            {
                return true;
            }
            else
            {
                return false;
            }
        }


        public void Clear()
        {
            rear = front = 0;
        }

        public bool In(object e)
        {
            if (IsFull())
            {
                return false;
            }
           
            rear = (rear + 1) % Max;
            data[rear] = e;
            return true;
            //rear = rear + 1;
        }

        public bool Out(ref object e)
        {
            e = null;
            if (IsEmpty())
            {
                return false;
            }

          
            front = (front + 1) % Max;//隊頭變成後面一位
            e = data[front];
            Doing = e;
            return true;
            //注釋部分為普通隊列操作。上面為循環隊列操作
            //if (rear - front > 0)
            //{
            //    object tmp = data[++front];
            //    Doing = tmp;
            //    return tmp;
            //}
            //else
            //{
            //    //全部出完了
            //    Clear();
            //    return null;

            //}
        }

        public object GetHead()
        {
            if (IsEmpty())
            {
                return null;
            }
            return data[(front + 1) % Max];
            //return data[front + 1];
        }

        public bool Exist(object e)
        {
            //for (int i = 0; i < Max; i++)
            //{
            //    if (data[i] != null && data[i].Equals(e))
            //    {
            //        return true;
            //    }
            //}
            if (IsEmpty())
            {
                return false;
            }

            int i = (front + 1) % Max;//Head
            while (i != (rear + 1) % Max)//End
            {
                if (data[i].Equals(e))
                {
                    return true;
                }

                i = (i + 1) % Max;
            }

            return false;
        }

        public int ExistCount(object e)
        {
            int Count = 0;
            if (IsEmpty())
            {
                return 0;
            }

            int i = (front + 1) % Max;//Head
            while (i != (rear + 1) % Max)//End
            {
                if (data[i].Equals(e))
                {
                    Count++;
                }

                i = (i + 1) % Max;
            }

            return Count;
        }

        public void Delete1(object e)
        {
            if (IsEmpty())
            {
                return;
            }
            int i = (front + 1) % Max;//隊頭
            while (i != (rear + 1) % Max)
            {
                if (data[i].Equals(e))
                {
                    #region 所有元素前移一位
                    int index = i % Max;
                    while (index != (rear) % Max)
                    {
                        data[index] = data[(index + 1) % Max];
                        index = (index + 1) % Max;
                    }

                    if (rear == 0)
                    {
                        rear = Max - 1;
                    }
                    else
                    {
                        rear = (rear - 1) % Max;
                    }

                    #endregion

                    break;
                }

                i = (i + 1) % Max;//i++
            }

        }

        public void DeleteAll(object e)
        {
            if (IsEmpty())
            {
                return;
            }

            int count = ExistCount(e);
            for (int i = 0; i < count; i++)
            {
                Delete1(e);
            }
        }

        public void ThrowToEnd(object e)
        {
            if (Exist(e))
            {
                Delete1(e);
                In(e);
            }
        }



        public bool Check()
        {
            return false;
        }

        //public bool CheckSignalValid(string position)
        //{
        //    if (ExistElement(position) || (Program.form1.bUROverAction == false && (DoingQueueElement.Position == position) && !Program.form1.Robot.bSkipCheck))
        //    {
        //        if (ExistElement(position))
        //        {
        //            AddURServerLog("Exist xinhao");
        //        }

        //        if (!Program.form1.bUROverAction)
        //        {
        //            AddURServerLog("not over");
        //        }


        //        if (DoingQueueElement.Position == position)
        //        {
        //            AddURServerLog("Doing");
        //        }

        //        Thread ArmTipThread = new Thread(new ThreadStart(ArmTip));
        //        ArmTipThread.Start();
        //        AddURServerLog("隊列中已有或者UR當前正在處理" + position + "號機信號，忽略該信號");
        //        return false;
        //    }
        //    else
        //    {
        //        return true;
        //    }
        //}


        //public bool EnQueue(ATS_Client.Action data)
        //{
        //    mutex.WaitOne();
        //    if (CheckSignalValid(data.Position))
        //    {

        //        #region Test GoldenSimple
        //        int iTemp = 0;
        //        if (int.TryParse(data.Position, out iTemp))
        //        {
        //            if (Program.form1.bPassGoldenSimpleMode)
        //            {
        //                if (Program.form1.ATS(iTemp.ToString()).bTestGoldenSimpleOver == true)
        //                {
        //                    AddURServerLog(data.Position + "號機Pass標準件測試已完成，在該模式下不接受信號");
        //                    mutex.ReleaseMutex();
        //                    return false;
        //                }
        //                else if (Program.form1.ATS(iTemp.ToString()).bTestPassGoldenSimple == true)
        //                {
        //                    if (Program.form1.ATS(iTemp.ToString()).bGoldenSimpleBarcode)
        //                    {
        //                        Program.form1.AddGoldenSimpleLog(data.Position + "號機Pass標準件測試完畢");
        //                        //Program.form1.SetGoldenDisplayStatus(data.Position, 1);
        //                        Program.form1.ATS(iTemp.ToString()).bTestPassGoldenSimple = false;
        //                        Program.form1.ATS(iTemp.ToString()).bTestGoldenSimpleOver = true;
        //                        mutex.ReleaseMutex();
        //                        return false;
        //                    }
        //                    else
        //                    {
        //                        Program.form1.AddGoldenSimpleLog(data.Position + "號機投入的不是標準件");
        //                        Program.form1.ATS(iTemp.ToString()).bTestGoldenSimpleOver = false;
        //                    }
        //                }
        //            }
        //            else if (Program.form1.bNGGoldenSimpleMode)
        //            {
        //                if (Program.form1.ATS(iTemp.ToString()).bTestGoldenSimpleOver == true)
        //                {
        //                    AddURServerLog(data.Position + "號機NG標準件測試已完成，在該模式下不接受信號");
        //                    mutex.ReleaseMutex();
        //                    return false;
        //                }
        //                else if (Program.form1.ATS(iTemp.ToString()).bTestNGGoldenSimple == true)
        //                {
        //                    if (Program.form1.ATS(iTemp.ToString()).bGoldenSimpleBarcode)
        //                    {
        //                        Program.form1.AddGoldenSimpleLog(data.Position + "號機NG標準件測試完畢");
        //                        //Program.form1.SetGoldenDisplayStatus(data.Position, 3);
        //                        Program.form1.ATS(iTemp.ToString()).bTestNGGoldenSimple = false;
        //                        Program.form1.ATS(iTemp.ToString()).bTestGoldenSimpleOver = true;
        //                        mutex.ReleaseMutex();
        //                        return false;
        //                    }
        //                    else
        //                    {
        //                        Program.form1.AddGoldenSimpleLog(data.Position + "號機投入的不是標準件");
        //                        Program.form1.ATS(iTemp.ToString()).bTestGoldenSimpleOver = false;
        //                    }
        //                }
        //            }
        //            else
        //            {
        //                //Program.form1.SetGoldenDisplayStatus("0", 0);
        //                Program.form1.ATS(iTemp.ToString()).bTestPassGoldenSimple = false;
        //                Program.form1.ATS(iTemp.ToString()).bTestNGGoldenSimple = false;
        //            }
        //        }
        //        #endregion

        //        if ((rear + 1) % Max != front)
        //        {
        //            rear = (rear + 1) % Max;
        //            list[rear] = data;

        //            Program.form1.ShowQueue(rear, 2);
        //            Count++;
        //            mutex.ReleaseMutex();
        //            return true;
        //        }
        //        else
        //        {
        //            AddURServerLog("入隊列失敗，隊列已滿！");
        //            mutex.ReleaseMutex();
        //            return false;
        //        }
        //    }
        //    else
        //    {
        //        mutex.ReleaseMutex();
        //        return false;
        //    }
        //}


        //public bool EnQueueNotCheck(ATS_Client.Action data)
        //{
        //    mutex.WaitOne();
        //    if ((rear + 1) % Max != front)
        //    {

        //        rear = (rear + 1) % Max;
        //        list[rear] = data;

        //        Program.form1.ShowQueue(rear, 2);
        //        Count++;
        //        mutex.ReleaseMutex();
        //        return true;
        //    }
        //    else
        //    {
        //        AddURServerLog("入隊列失敗，隊列已滿！");
        //        mutex.ReleaseMutex();
        //        return false;
        //    }
        //}
        //public bool DeQueue(ref ATS_Client.Action data)
        //{
        //    try
        //    {
        //        mutex.WaitOne();
        //        if (rear != front)
        //        {
        //            front = (front + 1) % Max;
        //            data = list[front];
        //            if (data.Position != null)
        //            {
        //                DoingQueueElement = data;
        //            }

        //            Program.form1.ShowQueue(front, 0);
        //            Count--;
        //            mutex.ReleaseMutex();
        //            return true;
        //        }
        //        else
        //        {
        //            mutex.ReleaseMutex();
        //            return false;
        //        }
        //    }
        //    catch (Exception e)
        //    {
        //        AddExceptionLog("[Queue]" + e.ToString());
        //        MessageBox.Show("出隊列異常" + e.ToString());
        //        mutex.ReleaseMutex();
        //        return false;
        //    }
        //}
        //public bool DeleteElement(string position)
        //{
        //    try
        //    {
        //        mutex.WaitOne();
        //        if (front == rear)
        //        {
        //            mutex.ReleaseMutex();
        //            return false;
        //        }
        //        int i = (front + 1) % Max;
        //        while (i != (rear + 1) % Max)
        //        {
        //            if (position == list[i].Position)
        //            {
        //                #region 所有元素前移一位
        //                int index = i % Max;
        //                while (index != (rear) % Max)
        //                {
        //                    list[index] = list[(index + 1) % Max];
        //                    Program.form1.ShowQueue(index, 1);
        //                    index = (index + 1) % Max;
        //                }

        //                Program.form1.ShowQueue(rear, 0);
        //                if (rear == 0)
        //                {
        //                    rear = Max - 1;
        //                }
        //                else
        //                {
        //                    rear = (rear - 1) % Max;
        //                }
        //                AddURServerLog("刪除" + position + "號機信號，index:" + i.ToString());
        //                Count--;
        //                #endregion

        //                break;
        //            }
        //            i++;
        //            i = i % Max;
        //        }
        //        mutex.ReleaseMutex();
        //        return false;
        //    }
        //    catch (Exception e)
        //    {

        //        mutex.ReleaseMutex();
        //        AddExceptionLog("[Queue]" + e.ToString());
        //        return false;
        //    }

        //}
        //public bool OutSpecifyElement(string[] positions, ref ATS_Client.Action data)
        //{
        //    try
        //    {
        //        mutex.WaitOne();
        //        if (front == rear)
        //        {
        //            mutex.ReleaseMutex();
        //            return false;
        //        }
        //        foreach (string position in positions)
        //        {
        //            int i = (front + 1) % Max;
        //            while (i != (rear + 1) % Max)
        //            {
        //                if (position == list[i].Position)
        //                {
        //                    data = list[i];
        //                    #region 所有元素前移一位
        //                    int index = i % Max;
        //                    while (index != (rear) % Max)
        //                    {
        //                        list[index] = list[(index + 1) % Max];
        //                        Program.form1.ShowQueue(index, 1);
        //                        index = (index + 1) % Max;
        //                    }
        //                    Program.form1.ShowQueue(rear, 0);
        //                    if (rear == 0)
        //                    {
        //                        rear = Max - 1;
        //                    }
        //                    else
        //                    {
        //                        rear = (rear - 1) % Max;
        //                    }
        //                    AddURServerLog("刪除" + position + "號機信號，index:" + i.ToString());
        //                    #endregion
        //                    Count--;
        //                    mutex.ReleaseMutex();
        //                    return true;
        //                }
        //                i++;
        //                i = i % Max;
        //            }
        //        }

        //        mutex.ReleaseMutex();
        //        return false;
        //    }
        //    catch (Exception e)
        //    {

        //        mutex.ReleaseMutex();
        //        AddExceptionLog("[Queue]" + e.ToString());
        //        return false;
        //    }

        //}
        //public bool DeleteElement(string position, URRobot.CMD URCmd)
        //{
        //    try
        //    {
        //        mutex.WaitOne();
        //        if (front == rear)
        //        {
        //            mutex.ReleaseMutex();
        //            return false;
        //        }

        //        int i = (front + 1) % Max;
        //        AddURServerLog("++++刪除條件i>=" + i + " i<" + (rear + 1) % Max);
        //        while (i != (rear + 1) % Max)
        //        {
        //            if (position == list[i].Position && URCmd == list[i].URCmd)
        //            {
        //                #region 所有元素前移一位
        //                int index = i % Max;
        //                while (index != rear % Max)
        //                {
        //                    list[index] = list[(index + 1) % Max];
        //                    Program.form1.ShowQueue(index, 1);
        //                    index = (index + 1) % Max;
        //                }
        //                Program.form1.ShowQueue(rear, 0);
        //                if (rear == 0)
        //                {
        //                    rear = Max - 1;
        //                }
        //                else
        //                {
        //                    rear = (rear - 1) % Max;
        //                }
        //                Count--;
        //                AddURServerLog("刪除" + position + "號機信號，index:" + i.ToString());

        //                #endregion
        //                break;
        //            }
        //            i++;
        //            i = i % Max;
        //        }
        //        mutex.ReleaseMutex();
        //        return false;
        //    }
        //    catch (Exception e)
        //    {

        //        mutex.ReleaseMutex();
        //        AddExceptionLog("[Queue]" + e.ToString());
        //        return false;
        //    }

        //}
        //public bool ExistElement(string position)
        //{
        //    try
        //    {

        //        if (front == rear)
        //        {

        //            return false;
        //        }
        //        int i = (front + 1) % Max;
        //        while (i != (rear + 1) % Max)
        //        {
        //            if (position == list[i].Position)
        //            {
        //                //AddURServerLog("Exist!!!");
        //                return true;
        //            }
        //            i++;
        //            i = i % Max;
        //        }

        //        return false;
        //    }
        //    catch (Exception e)
        //    {

        //        mutex.ReleaseMutex();
        //        AddExceptionLog("[Queue]" + e.ToString());
        //        return false;
        //    }
        //}


        //public bool ExistElement(string position, ref ATS_Client.Action ac)
        //{
        //    try
        //    {
        //        ac = new ATS_Client.Action();
        //        if (front == rear)
        //        {

        //            return false;
        //        }
        //        int i = (front + 1) % Max;
        //        while (i != (rear + 1) % Max)
        //        {
        //            if (position == list[i].Position)
        //            {
        //                //AddURServerLog("Exist!!!");
        //                ac = list[i];
        //                return true;
        //            }
        //            i++;
        //            i = i % Max;
        //        }

        //        return false;
        //    }
        //    catch (Exception e)
        //    {

        //        mutex.ReleaseMutex();
        //        AddExceptionLog("[Queue]" + e.ToString());
        //        return false;
        //    }
        //}




    }
}
