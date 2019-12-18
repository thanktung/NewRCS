using System;
using System.Collections.Generic;
using System.Text;
using AutoMationTest.UI;
using System.Threading;
using AutoMationTest.Common;

namespace AutoMationTest.Function
{
    public class ATSQueue
    {

        //如果是普通隊列，新增元素，隊尾rear只用加1就行；如果是循環隊列，rear + 1後求Max的餘數
        //簡單來說，普通隊列任何計算的 x++ 就等於循環隊列的 （x+1) % max
        public Mutex mutex;
        TestUI.Action[] data;//數據元素
        private int Max;//最大容量
        private int front;//指向隊頭
        private int rear;//指向隊尾
        //public bool bChanged = false;
        public TestUI.Action Doing;
        public int Count;

        TestUI.Action NULLData;

        public ATSQueue(int Max)
        {
            this.Max = Max;
            front = rear = 0; //此處為循環隊列，普通隊列為-1；
            data = new TestUI.Action[Max];
            mutex = new Mutex();
            NULLData = new TestUI.Action();

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

        public TestUI.Action this[int index]
        {
            get
            {

                if (IsEmpty())
                {
                    return NULLData;
                }

                int addindex = 0;
                int i = (front + 1) % Max;

                while (i != (rear + 1) % Max)
                {
                    if (index == addindex)
                    {
                        TestUI.Action temp = data[i];
                        return temp;
                    }
                    i = (i + 1) % Max;
                    addindex++;
                }

                return NULLData;
            }

        }

        public int GetQueueLength()
        {
            int m = (rear - front + Max) % Max;
            //if (Common.Produce.showQueue != null)
            //{
            //    Common.Produce.showQueue.ShowQueueCount(m);
            //}

            return m;
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

        public bool In(TestUI.Action e)
        {
            mutex.WaitOne();

            if (IsFull())
            {
                mutex.ReleaseMutex();
                return false;
            }


            rear = (rear + 1) % Max;
            data[rear] = e;


            mutex.ReleaseMutex();
            return true;

        }

        public bool In_Check(TestUI.Action e)
        {
            mutex.WaitOne();
            if (IsFull() || !Check(e.StationNumber))
            {
                mutex.ReleaseMutex();
                return false;
            }

            rear = (rear + 1) % Max;
            data[rear] = e;
            mutex.ReleaseMutex();

            return true;

        }

        public bool Out(ref TestUI.Action e)
        {
            mutex.WaitOne();

            if (IsEmpty())
            {
                mutex.ReleaseMutex();
                return false;
            }


            front = (front + 1) % Max;//隊頭變成後面一位
            e = data[front];
            Doing = e;

            mutex.ReleaseMutex();
            return true;

        }

        public TestUI.Action GetHead()
        {
            if (IsEmpty())
            {
                return NULLData;
            }
            return data[(front + 1) % Max];
        }

        public bool Exist(string StationNum)
        {

            if (IsEmpty())
            {
                return false;
            }

            int i = (front + 1) % Max;//Head
            while (i != (rear + 1) % Max)//End
            {
                if (data[i].StationNumber.Equals(StationNum))
                {
                    return true;
                }

                i = (i + 1) % Max;
            }

            return false;
        }

        public bool Exist(int StationNum, Produce.RobotCMD cmd)
        {

            if (IsEmpty())
            {
                return false;
            }

            int i = (front + 1) % Max;//Head
            while (i != (rear + 1) % Max)//End
            {
                if (data[i].StationNumber.Equals(StationNum.ToString()) && data[i].robotCmd == cmd)
                {
                    return true;
                }

                i = (i + 1) % Max;
            }

            return false;
        }

        public bool Exist(TestUI.Action e)
        {
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

        public int ExistCount(TestUI.Action e)
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

        public void Delete(TestUI.Action e)
        {
            mutex.WaitOne();
            if (IsEmpty())
            {
                mutex.ReleaseMutex();
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
            //if (Common.Produce.showQueue != null)
            //{
            //    for (int m = 0; m < GetQueueLength(); m++)
            //    {
            //        Common.Produce.showQueue.SetQueueStatus(m + 1, this[m]);
            //    }
            //}
            mutex.ReleaseMutex();
        }

        public void Delete(string StationNum)
        {
            mutex.WaitOne();
            if (IsEmpty())
            {
                mutex.ReleaseMutex();
                return;
            }
            int i = (front + 1) % Max;//隊頭
            while (i != (rear + 1) % Max)
            {
                if (data[i].StationNumber.Equals(StationNum))
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
            //if (Common.Produce.showQueue != null)
            //{
            //    for (int m = 0; m < GetQueueLength(); m++)
            //    {
            //        Common.Produce.showQueue.SetQueueStatus(m + 1, this[m]);
            //    }
            //}
            mutex.ReleaseMutex();
        }


        public void ThrowToEnd(TestUI.Action e)
        {
            if (Exist(e))
            {
                Delete(e);
                In(e);
            }
        }



        public bool Check(string StationNum)
        {
            int index = Convert.ToInt16(Common.Produce.Station.Index[Convert.ToInt32(StationNum)]);

            if (Exist(StationNum) || (Robots.Robot.RobotDoingStation.Contains(StationNum)))// && !Produce.RobotDoneOver_ByStation[index]))
            {
                return false;
            }

            return true;
        }

    }
}
