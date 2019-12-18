using System;
using System.Collections.Generic;
using System.Text;
using System.Collections;

namespace AutoMationTest.Function
{
    public class SortFunc
    {

        public static void SortGuluGulu(int[] arr)
        {
            int temp = 0;

            for (int i = 0; i < arr.Length - 1; i++)
            {
                #region 将大的数字移到数组的arr.Length-1-i

                for (int j = 0; j < arr.Length - 1 - i; j++)
                {
                    if (arr[j] > arr[j + 1])
                    {
                        temp = arr[j + 1];
                        arr[j + 1] = arr[j];
                        arr[j] = temp;
                    }
                }
                #endregion
            }
        }

        public static int[] SortGuluGuluHash(Hashtable ht)
        {
            int temp = 0;
            int tempkey = 0;
            int[] keyArray = new int[ht.Count];
            int[] valueArray = new int[ht.Count];

            ht.Keys.CopyTo(keyArray, 0);
            ht.Values.CopyTo(valueArray, 0);

            for (int i = 0; i < valueArray.Length - 1; i++)
            {
                #region 将大的数字移到数组的arr.Length-1-i

                for (int j = 0; j < valueArray.Length - 1 - i; j++)
                {
                    if (valueArray[j] > valueArray[j + 1])
                    {
                        temp = valueArray[j + 1];
                        valueArray[j + 1] = valueArray[j];
                        valueArray[j] = temp;

                        tempkey = keyArray[j + 1];
                        keyArray[j + 1] = keyArray[j];
                        keyArray[j] = tempkey;
                    }
                }
                #endregion
            }

            return keyArray;
        }

        public static string[] SortHashTable(Hashtable ht)
        {
            //先定义两个一维数组，分别用来存储Key和Value
            string[] keyArray = new string[ht.Count];
            int[] valueArray = new int[ht.Count];

            //将HashTable中的Key和Value分别赋给上面两个数组
            ht.Keys.CopyTo(keyArray, 0);
            ht.Values.CopyTo(valueArray, 0);

            //下面就是对Value进行排序，当然需要按排序结果将Keys的值也作对应的排列
            //Sort默认是升序排序，如果想用降序排序请在Sort排序后使用Array.Reverse()进行反向排序
            Array.Sort(valueArray, keyArray);
            return keyArray;
        }

        public static int[] SortHashTable2(Hashtable ht)
        {
            //先定义两个一维数组，分别用来存储Key和Value
            int[] keyArray = new int[ht.Count];
            int[] valueArray = new int[ht.Count];

            //将HashTable中的Key和Value分别赋给上面两个数组
            ht.Keys.CopyTo(keyArray, 0);
            ht.Values.CopyTo(valueArray, 0);

            //下面就是对Value进行排序，当然需要按排序结果将Keys的值也作对应的排列
            //Sort默认是升序排序，如果想用降序排序请在Sort排序后使用Array.Reverse()进行反向排序
            Array.Sort(valueArray, keyArray);
            return keyArray;
        }

        public static int[] SortFR(Hashtable ht)
        {
            //先定义两个一维数组，分别用来存储Key和Value
            int[] keyArray = new int[ht.Count];
            double[] valueArray = new double[ht.Count];

            //将HashTable中的Key和Value分别赋给上面两个数组
            ht.Keys.CopyTo(keyArray, 0);
            ht.Values.CopyTo(valueArray, 0);

            //下面就是对Value进行排序，当然需要按排序结果将Keys的值也作对应的排列
            //Sort默认是升序排序，如果想用降序排序请在Sort排序后使用Array.Reverse()进行反向排序
            Array.Sort(valueArray, keyArray);
            return keyArray;
        }


        public static int[] SortArray(ArrayList al1, ArrayList al2)
        {
            //先定义两个一维数组，分别用来存储Key和Value
            int[] keyArray = new int[al1.Count];
            int[] valueArray = new int[al2.Count];

            //将HashTable中的Key和Value分别赋给上面两个数组
            al1.CopyTo(keyArray, 0);
            al2.CopyTo(valueArray, 0);

            //下面就是对Value进行排序，当然需要按排序结果将Keys的值也作对应的排列
            //Sort默认是升序排序，如果想用降序排序请在Sort排序后使用Array.Reverse()进行反向排序
            Array.Sort(valueArray, keyArray);
            return keyArray;
        }

        public static int[] SortArray2(ArrayList al1, ArrayList al2)
        {
            //先定义两个一维数组，分别用来存储Key和Value
            int[] keyArray = new int[al1.Count];
            double[] valueArray = new double[al2.Count];

            //将HashTable中的Key和Value分别赋给上面两个数组
            al1.CopyTo(keyArray, 0);
            al2.CopyTo(valueArray, 0);

            //下面就是对Value进行排序，当然需要按排序结果将Keys的值也作对应的排列
            //Sort默认是升序排序，如果想用降序排序请在Sort排序后使用Array.Reverse()进行反向排序
            Array.Sort(valueArray, keyArray);
            return keyArray;
        }

        public static int[] SortArrayGulu(ArrayList al1, ArrayList al2)
        {
            int temp = 0;
            int tempkey = 0;

            //先定义两个一维数组，分别用来存储Key和Value
            int[] keyArray = new int[al1.Count];
            int[] valueArray = new int[al2.Count];

            //将HashTable中的Key和Value分别赋给上面两个数组
            al1.CopyTo(keyArray, 0);
            al2.CopyTo(valueArray, 0);

            for (int i = 0; i < valueArray.Length - 1; i++)
            {
                #region 将大的数字移到数组的arr.Length-1-i

                for (int j = 0; j < valueArray.Length - 1 - i; j++)
                {
                    if (valueArray[j] > valueArray[j + 1])
                    {
                        temp = valueArray[j + 1];
                        valueArray[j + 1] = valueArray[j];
                        valueArray[j] = temp;

                        tempkey = keyArray[j + 1];
                        keyArray[j + 1] = keyArray[j];
                        keyArray[j] = tempkey;
                    }
                }
                #endregion
            }


            ////下面就是对Value进行排序，当然需要按排序结果将Keys的值也作对应的排列
            ////Sort默认是升序排序，如果想用降序排序请在Sort排序后使用Array.Reverse()进行反向排序
            //Array.Sort(valueArray, keyArray);
            return keyArray;
        }

        public static int[] SortArray2Gulu(ArrayList al1, ArrayList al2)
        {
            double temp = 0;
            int tempkey = 0;

            //先定义两个一维数组，分别用来存储Key和Value
            int[] keyArray = new int[al1.Count];
            double[] valueArray = new double[al2.Count];

            //将HashTable中的Key和Value分别赋给上面两个数组
            al1.CopyTo(keyArray, 0);
            al2.CopyTo(valueArray, 0);

            //下面就是对Value进行排序，当然需要按排序结果将Keys的值也作对应的排列
            //Sort默认是升序排序，如果想用降序排序请在Sort排序后使用Array.Reverse()进行反向排序
            //Array.Sort(valueArray, keyArray);


            for (int i = 0; i < valueArray.Length - 1; i++)
            {
                #region 将大的数字移到数组的arr.Length-1-i

                for (int j = 0; j < valueArray.Length - 1 - i; j++)
                {
                    if (valueArray[j] > valueArray[j + 1])
                    {
                        temp = valueArray[j + 1];
                        valueArray[j + 1] = valueArray[j];
                        valueArray[j] = temp;

                        tempkey = keyArray[j + 1];
                        keyArray[j + 1] = keyArray[j];
                        keyArray[j] = tempkey;
                    }
                }
                #endregion
            }

            return keyArray;
        }

    }
}
