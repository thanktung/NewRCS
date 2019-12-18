using System;
using System.Collections.Generic;
using System.Drawing;
using PylonC.NET;
using PylonC.NETSupportLibrary;

namespace AutoMationTest.AVI.Basler
{
    public class BaslerCtrl
    {
        private string name = "ExposureTimeRaw"; /* The name of the node. */
        private NODE_CALLBACK_HANDLE m_hCallbackHandle = new NODE_CALLBACK_HANDLE(); /* The handle of the node callback. */
        private NodeCallbackHandler m_nodeCallbackHandler = new NodeCallbackHandler(); /* The callback handler. */
        private NODE_HANDLE m_hNode = new NODE_HANDLE(); /* The handle of the node. */


        private string name1 = "Width"; /* The name of the node. */
        private NODE_CALLBACK_HANDLE m_hCallbackHandle1 = new NODE_CALLBACK_HANDLE(); /* The handle of the node callback. */
        private NodeCallbackHandler m_nodeCallbackHandler1 = new NodeCallbackHandler(); /* The callback handler. */
        private NODE_HANDLE m_hNode_width = new NODE_HANDLE(); /* The handle of the node. */

        private string name2 = "Height"; /* The name of the node. */
        private NODE_CALLBACK_HANDLE m_hCallbackHandle2 = new NODE_CALLBACK_HANDLE(); /* The handle of the node callback. */
        private NodeCallbackHandler m_nodeCallbackHandler2 = new NodeCallbackHandler(); /* The callback handler. */
        private NODE_HANDLE m_hNode_height = new NODE_HANDLE(); /* The handle of the node. */


        private string name3 = "CenterX"; /* The name of the node. */
        private NODE_CALLBACK_HANDLE m_hCallbackHandle3 = new NODE_CALLBACK_HANDLE(); /* The handle of the node callback. */
        private NodeCallbackHandler m_nodeCallbackHandler3 = new NodeCallbackHandler(); /* The callback handler. */
        private NODE_HANDLE m_hNode_centerX = new NODE_HANDLE(); /* The handle of the node. */

        private string name4 = "CenterY"; /* The name of the node. */
        private NODE_CALLBACK_HANDLE m_hCallbackHandle4 = new NODE_CALLBACK_HANDLE(); /* The handle of the node callback. */
        private NodeCallbackHandler m_nodeCallbackHandler4 = new NodeCallbackHandler(); /* The callback handler. */
        private NODE_HANDLE m_hNode_centerY = new NODE_HANDLE(); /* The handle of the node. */

        public long ExposureValue;
        public int Width;
        public int Height;
        public bool bCenterX;
        public bool bCenterY;
        private List<string> deviceNameList = null;

        private int m_MinExposureTimeScale;
        //Camera对象
        public ImageProvider m_imageProvider;
        //Camera设备名
        private DeviceEnumerator.Device m_Device;
        //所有Camera设备
        private List<DeviceEnumerator.Device> m_Devices;

        private Bitmap m_ShotMap;
        /// <summary>
        /// 图像
        /// </summary>
        public Bitmap ShotImage
        {
            get { return this.m_ShotMap; }
            set { this.m_ShotMap = value; }
        }

        private List<string> deviceNames = null;
        /// <summary>
        /// 设备名称集合
        /// </summary>
        public List<string> DeviceNames
        {
            get { return this.deviceNames; }
        }

        public  void InitialBasler()
        {
            Environment.SetEnvironmentVariable("PYLON_GIGE_HEARTBEAT", "300000" /*ms*/);
            Pylon.Initialize();

            deviceNameList = RefreshDevices();

        }

        public BaslerCtrl()
        {
            m_imageProvider = new ImageProvider();
            m_imageProvider.ImageReadyEvent += new ImageProvider.ImageReadyEventHandler(OnImageReadyEventCallback);
        }

        private void OnImageReadyEventCallback()
        {
            if (m_imageProvider == null)
            {
                return;
            }

            try
            {
                //获取图片(ImageProvider grab已将图像插入队列中)
                ImageProvider.Image image = m_imageProvider.GetCurrentImage();
                //当图像Buffer不为0时
                if (image != null)
                {
                    //查看图像是否适用的（参数是否匹配--->是否实例化、宽、高、颜色模型是否都匹配）
                    bool isCompatible = BitmapFactory.IsCompatible(m_ShotMap, image.Width, image.Height, image.Color);
                    if (!isCompatible)
                        BitmapFactory.CreateBitmap(out m_ShotMap, image.Width, image.Height, image.Color);
                    //适用，则直接用该Bitmap容器装入Buffer
                    BitmapFactory.UpdateBitmap(m_ShotMap, image.Buffer, image.Width, image.Height, image.Color);
                }
                //释放Provider中的图像Buffer
                m_imageProvider.ReleaseImage();
            }
            catch (Exception ex)
            { }
        }

        /// <summary>
        /// 打开相机
        /// </summary>
        public void Open()
        {

            m_imageProvider.Open(this.m_Device.Index);

            #region 曝光节点
            //初始化曝光节点
            m_hNode = m_imageProvider.GetNodeFromDevice(name);
            if (!m_hNode.IsValid /* No node has been found using the provided name. */
                   && (name == "GainRaw" || name == "ExposureTimeRaw")) /* This means probably that the camera is compliant to a later SFNC version. */
            {
                /* Check to see if a compatible node exists. The SFNC 2.0, implemented by Basler USB Cameras for instance, defines Gain
                   and ExposureTime as features of type Float.*/
                if (name == "GainRaw")
                {
                    m_hNode = m_imageProvider.GetNodeFromDevice("Gain");
                }
                else if (name == "ExposureTimeRaw")
                {
                    m_hNode = m_imageProvider.GetNodeFromDevice("ExposureTime");
                }
                /* The underlying integer representation of Gain and ExposureTime can be accessed using
                   the so called alias node. The alias is another representation of the original parameter.
                       
                   Since this slider control can only be used with Integer nodes we have to use
                   the alias node here to display and modify Gain and ExposureTime.
                */
                m_hNode = GenApi.NodeGetAlias(m_hNode);
                /* Register for changes. */
                m_hCallbackHandle = GenApi.NodeRegisterCallback(m_hNode, m_nodeCallbackHandler);
            }
            else
            {
                /* Register for changes. */
                m_hCallbackHandle = GenApi.NodeRegisterCallback(m_hNode, m_nodeCallbackHandler);
            }
            #endregion

            //获取曝光参数
            if (m_hNode.IsValid)
            {
                if (GenApi.NodeGetType(m_hNode) == EGenApiNodeType.IntegerNode)  /* Check if proper node type. */
                {
                    /* Get the values. */
                    bool writable = GenApi.NodeIsWritable(m_hNode);
                    long min = checked((int)GenApi.IntegerGetMin(m_hNode));
                    long max = checked((int)GenApi.IntegerGetMax(m_hNode));
                    long val = checked((int)GenApi.IntegerGetValue(m_hNode));
                    ExposureValue = val;
                    int inc = checked((int)GenApi.IntegerGetInc(m_hNode));
                    m_MinExposureTimeScale = inc;

                    //return;
                }
            }

            m_hNode_width = m_imageProvider.GetNodeFromDevice(name1);
            if (!m_hNode_width.IsValid) /* This means probably that the camera is compliant to a later SFNC version. */
            {
                m_hNode_width = m_imageProvider.GetNodeFromDevice("Width");
                m_hNode_width = GenApi.NodeGetAlias(m_hNode_width);
                /* Register for changes. */
                m_hCallbackHandle1 = GenApi.NodeRegisterCallback(m_hNode_width, m_nodeCallbackHandler1);
            }
            else
            {
                m_hCallbackHandle1 = GenApi.NodeRegisterCallback(m_hNode_width, m_nodeCallbackHandler1);
            }

            if (m_hNode_width.IsValid)
            {
                if (GenApi.NodeGetType(m_hNode_width) == EGenApiNodeType.IntegerNode)  /* Check if proper node type. */
                {
                    int val = checked((int)GenApi.IntegerGetValue(m_hNode_width));
                    Width = val;
                }
            }


            m_hNode_height = m_imageProvider.GetNodeFromDevice(name2);
            if (!m_hNode_height.IsValid) /* This means probably that the camera is compliant to a later SFNC version. */
            {
                m_hNode_height = m_imageProvider.GetNodeFromDevice("Height");
                m_hNode_height = GenApi.NodeGetAlias(m_hNode_height);
                /* Register for changes. */
                m_hCallbackHandle2 = GenApi.NodeRegisterCallback(m_hNode_height, m_nodeCallbackHandler2);
            }
            else
            {
                m_hCallbackHandle2 = GenApi.NodeRegisterCallback(m_hNode_height, m_nodeCallbackHandler2);
            }

            if (m_hNode_height.IsValid)
            {
                if (GenApi.NodeGetType(m_hNode_height) == EGenApiNodeType.IntegerNode)  /* Check if proper node type. */
                {
                    int val = checked((int)GenApi.IntegerGetValue(m_hNode_height));
                    Height = val;
                }
            }



            m_hNode_centerX = m_imageProvider.GetNodeFromDevice(name3);
            if (!m_hNode_centerX.IsValid) /* This means probably that the camera is compliant to a later SFNC version. */
            {
                m_hNode_centerX = m_imageProvider.GetNodeFromDevice("CenterX");
                m_hNode_centerX = GenApi.NodeGetAlias(m_hNode_centerX);
                /* Register for changes. */
                m_hCallbackHandle3 = GenApi.NodeRegisterCallback(m_hNode_centerX, m_nodeCallbackHandler3);
            }
            else
            {
                m_hCallbackHandle3 = GenApi.NodeRegisterCallback(m_hNode_centerX, m_nodeCallbackHandler3);
            }

            if (m_hNode_centerX.IsValid)
            {
                if (GenApi.NodeGetType(m_hNode_centerX) == EGenApiNodeType.BooleanNode)  /* Check if proper node type. */
                {
                    bool val = checked((bool)GenApi.BooleanGetValue(m_hNode_centerX));
                    bCenterX = val;
                }
            }


            m_hNode_centerY = m_imageProvider.GetNodeFromDevice(name4);
            if (!m_hNode_centerY.IsValid) /* This means probably that the camera is compliant to a later SFNC version. */
            {
                m_hNode_centerY = m_imageProvider.GetNodeFromDevice("CenterY");
                m_hNode_centerY = GenApi.NodeGetAlias(m_hNode_centerY);
                /* Register for changes. */
                m_hCallbackHandle4 = GenApi.NodeRegisterCallback(m_hNode_centerY, m_nodeCallbackHandler4);
            }
            else
            {
                m_hCallbackHandle4 = GenApi.NodeRegisterCallback(m_hNode_centerY, m_nodeCallbackHandler4);
            }

            if (m_hNode_centerY.IsValid)
            {
                if (GenApi.NodeGetType(m_hNode_centerY) == EGenApiNodeType.BooleanNode)  /* Check if proper node type. */
                {
                    bool val = checked((bool)GenApi.BooleanGetValue(m_hNode_centerY));
                    bCenterY = val;
                }
            }
        }

        /// <summary>
        /// 单次取图
        /// </summary>
        public void OneShot()
        {
            m_imageProvider.OneShot();

        }

        /// <summary>
        /// 连续取图
        /// </summary>
        public void ContinuesShot()
        {
            m_imageProvider.ContinuousShot();
        }

        /// <summary>
        /// 停止取图
        /// </summary>
        public void Stop()
        {
            m_imageProvider.Stop();
        }

        /// <summary>
        /// 释放资源
        /// </summary>
        public void Dispose()
        {
            try
            {
                m_imageProvider.Stop();

            }
            catch (Exception ex)
            { }

            if (m_imageProvider.IsOpen) m_imageProvider.Close();

            m_imageProvider.ReleaseImage();

            m_imageProvider.Close();

            m_imageProvider = null;



            Pylon.Terminate();
        }

        /// <summary>
        /// 刷新相机设备
        /// </summary>
        public List<string> RefreshDevices()
        {
            m_Devices = DeviceEnumerator.EnumerateDevices();
            if (m_Devices.Count == 0)
                return null;

            deviceNames = new List<string>();
            for (int i = 0; i < m_Devices.Count; i++)
            {
                deviceNames.Add(m_Devices[i].Name);
            }

            return deviceNames;
        }

        /// <summary>
        /// 选择相机设备
        /// </summary>
        /// <param name="index"></param>
        public void SelectDevice(int index)
        {
            if (index < 0 || index > m_Devices.Count - 1)
                return;
            this.m_Device = m_Devices[index];
        }

        /// <summary>
        /// 设定曝光时间
        /// </summary>
        /// <param name="value"></param>
        public void SetExposureTime(long value)
        {
            if (m_hNode.IsValid)
            {
                try
                {
                    if (GenApi.NodeIsWritable(m_hNode))
                    {
                        value = (value / m_MinExposureTimeScale) * m_MinExposureTimeScale;
                        /* Set the value. */
                        GenApi.IntegerSetValue(m_hNode, value);
                        ExposureValue = value;
                    }
                }
                catch
                {
                    /* Ignore any errors here. */
                }
            }
        }


        public void SetSize(int value1, int value2, bool checked1, bool checked2)
        {
            if (m_hNode_width.IsValid && m_hNode_height.IsValid && m_hNode_centerX.IsValid && m_hNode_centerY.IsValid)
            {
                try
                {
                    if (GenApi.NodeIsWritable(m_hNode_width))
                    {
                        /* Set the value. */
                        GenApi.IntegerSetValue(m_hNode_width, value1);
                        Width = value1;
                    }

                    if (GenApi.NodeIsWritable(m_hNode_height))
                    {
                        /* Set the value. */
                        GenApi.IntegerSetValue(m_hNode_height, value2);
                        Height = value2;
                    }

                    if (GenApi.NodeIsWritable(m_hNode_centerX))
                    {
                        /* Set the value. */
                        GenApi.BooleanSetValue(m_hNode_centerX, checked1);
                        bCenterX = checked1;
                    }

                    if (GenApi.NodeIsWritable(m_hNode_centerY))
                    {
                        /* Set the value. */
                        GenApi.BooleanSetValue(m_hNode_centerY, checked2);
                        bCenterY = checked2;
                    }
                }
                catch
                {
                    /* Ignore any errors here. */
                }
            }
        }

    }
}
