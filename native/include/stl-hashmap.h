#ifndef STL_HASHMAP_H_
#define STL_HASHMAP_H_

#ifdef CONFIG_USE_0X
#include <unordered_map>
#define hashmap std::unordered_map
#else
#include <ext/hash_map>

namespace __gnu_cxx
{
template<>
struct hash<long long int>
{
	size_t operator()(long long int __x) const
	{
		return __x;
	}
};

template<>
struct hash<unsigned long long int>
{
	size_t operator()(unsigned long long int __x) const
	{
		return __x;
	}
};

};

#define hashmap __gnu_cxx::hash_map
#endif

#endif
